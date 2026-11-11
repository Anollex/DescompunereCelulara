"""Punctul de intrare: fereastra, starea interfeței și bucla principală.

Calculul propriu-zis (descompunere, căutare) stă în simulation.py și modulele lui;
aici doar se citesc intrările utilizatorului și se desenează.

Taburi:
    grid     - metoda omogenă: harta + matricea
    tree     - metoda arborelui: harta + graful frunzelor libere
    compare  - ambele metode pe aceeași hartă, cu aceleași puncte
    builder  - editorul de hărți (MapBuilder/map_builder.py)

Există o singură simulare pentru fiecare metodă. Tabul de comparație le arată pe
amândouă, deci ce rulezi acolo se vede apoi în detaliu în tabul metodei.
"""
import warnings

import pygame

from config import AUTO_STEP_MS, CURVE_SAMPLES, MAPS_DIR, MIN_SIZE, NOTICE_MS, THEMES
from geometry import obstacles_geometry, point_on_obstacle
from layout import make_layout
from MapBuilder.map_builder import MapBuilder
from map_view import MapView, draw_map
from model import FINISH, START
from render import (draw_cells_overlay, draw_leaf_graph, draw_marker, draw_matrix,
                    draw_notice, draw_stats_table)
from simulation import SimParams, Simulation
from svg_loader import list_maps, load_map
from widgets import (Slider, draw_button, draw_centered_text, draw_panel, draw_theme_button,
                     panel_content, uniform_font)

TABS = [("grid", "Metoda Omogena"), ("tree", "Metoda Arborelui"),
        ("compare", "Comparatie"), ("builder", "Map Builder")]
ACTIVE_SIMS = {"grid": ["grid"], "tree": ["tree"], "compare": ["grid", "tree"], "builder": []}
MAP_PANELS = {"grid": ["map"], "tree": ["map"], "compare": ["map", "panel"], "builder": []}


def set_minimum_window_size(size):
    """Spune sistemului de ferestre dimensiunea minimă permisă (necesită pygame-ce)."""
    if hasattr(pygame.display, "get_window"):          # versiunile noi de pygame-ce
        window = pygame.display.get_window()
    else:                                              # pygame-ce 2.5.x
        with warnings.catch_warnings():
            # avertismentul e despre desenarea prin Window; noi doar setăm o proprietate
            warnings.simplefilter("ignore", DeprecationWarning)
            window = pygame.Window.from_display_module()
    window.minimum_size = size


class MapLibrary:
    """Lista hărților din maps/; fiecare hartă se parsează o singură dată, la prima folosire."""

    def __init__(self, folder):
        self.folder = folder
        self.files = list_maps(folder)
        self.index = 0
        self._cache = {}          # cale -> MapData sau mesaj de eroare (str)
        self._geometry = {}       # cale -> reuniunea obstacolelor (shapely)

    def next(self):
        if self.files:
            self.index = (self.index + 1) % len(self.files)

    def path(self):
        return self.files[self.index] if self.files else None

    def name(self):
        return self.files[self.index].stem if self.files else "-"

    def current(self):
        """Întoarce MapData sau un str cu mesajul de eroare."""
        if not self.files:
            return f"Nicio harta .svg in {MAPS_DIR.name}/"
        path = self.files[self.index]
        if path not in self._cache:
            try:
                self._cache[path] = load_map(path, CURVE_SAMPLES)
            except Exception as exc:                   # un SVG stricat nu oprește aplicația
                print(f"Eroare la {path.name}: {exc}")
                self._cache[path] = f"Nu pot citi {path.name}"
        return self._cache[path]

    def on_obstacle(self, point):
        """True dacă punctul (coordonate de hartă) cade pe un obstacol al hărții curente."""
        data = self.current()
        if isinstance(data, str):
            return False
        path = self.path()
        if path not in self._geometry:
            self._geometry[path] = obstacles_geometry(data)
        return point_on_obstacle(self._geometry[path], point)

    def refresh(self, selected_path=None):
        """Recitește folderul după ce Map Builder salvează o hartă și o selectează pe cea nouă."""
        current = selected_path or self.path()
        self.files = list_maps(self.folder)
        self._cache = {path: value for path, value in self._cache.items() if path in self.files}
        self._geometry = {path: value for path, value in self._geometry.items() if path in self.files}
        if not self.files:
            self.index = 0
        elif current in self.files:
            self.index = self.files.index(current)
        else:
            self.index = min(self.index, len(self.files) - 1)


def map_views(tab, layout, current_map):
    """Câte un MapView pentru fiecare panou care arată harta în tabul curent."""
    if isinstance(current_map, str):
        return {}
    return {key: MapView(current_map.bounds,
                         panel_content(layout[key], layout["border"], layout["label_size"]))
            for key in MAP_PANELS[tab]}


def slider_rects(tab, layout):
    """Sliderele vizibile în tabul curent și dreptunghiul fiecăruia."""
    if tab == "grid":
        return {"slider_x": layout["slider_x"], "slider_y": layout["slider_y"]}
    if tab == "tree":
        return {"slider_depth": layout["slider_depth"]}
    if tab == "compare":
        return dict(zip(("slider_x", "slider_y", "slider_depth"), layout["cmp_sliders"]))
    return {}


def fmt(value, digits=0):
    return "-" if value is None else f"{value:.{digits}f}"


def comparison_rows(*all_stats):
    """Rândurile tabelului de comparație: (etichetă, valoare pe metodă, ...)."""
    def cells(s):
        return "-" if s["cells"] is None else f"{s['free']} / {s['cells']}"
    return [
        ("Celule libere / total", *[cells(s) for s in all_stats]),
        ("Muchii in graf", *[fmt(s["edges"]) for s in all_stats]),
        ("Pasi facuti", *[fmt(s["steps"]) for s in all_stats]),
        ("Noduri extinse", *[fmt(s["visited"]) for s in all_stats]),
        ("Celule pe drum", *[fmt(s["path_cells"]) for s in all_stats]),
        ("Lungime drum", *[fmt(s["path_length"], 1) for s in all_stats]),
    ]


pygame.init()
screen = pygame.display.set_mode(MIN_SIZE, pygame.RESIZABLE)
set_minimum_window_size(MIN_SIZE)
pygame.display.set_caption("Descompunere celulara")
clock = pygame.time.Clock()

alive = True
tab = "grid"           # unul dintre numele din TABS
theme = "light"        # "light" / "dark"
maps = MapLibrary(MAPS_DIR)
builder = MapBuilder(on_saved=lambda path: maps.refresh(path))
point_mode = "start"   # ce punct pui la click pe hartă: "start" / "finish"
start = None           # punctele, în coordonate de HARTĂ
finish = None
points_path = maps.path()   # harta pentru care sunt valabile start și finish
auto_running = False
last_auto_step = 0     # momentul (ms) ultimului pas făcut de AUTO
notice = ("", 0)       # (mesaj, momentul până la care se afișează)
sims = {"grid": Simulation(), "tree": Simulation()}

# create o singură dată, ca să-și păstreze valoarea când schimbi tabul
sliders = {
    "slider_x":     Slider("Celule X", 5, 20, 10),
    "slider_y":     Slider("Celule Y", 5, 20, 10),
    "slider_depth": Slider("Adancime", 2, 8, 4),
}

while alive:
    # 1. dimensiuni calculate din fereastră și harta curentă, înainte de evenimente
    w, h = screen.get_size()
    layout = make_layout(w, h)
    border = layout["border"]
    size = layout["label_size"]
    now = pygame.time.get_ticks()

    if maps.path() != points_path:          # harta s-a schimbat (de ex. salvare din Map Builder)
        start = finish = None               # punctele hărții vechi nu mai au sens
        points_path = maps.path()
    current_map = maps.current()            # MapData, sau un mesaj de eroare (str)
    views = map_views(tab, layout, current_map)

    # 2. evenimente
    step_requested = False
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            alive = False
            continue
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            # bara de sus e comună tuturor taburilor
            clicked = next((name for (name, _), rect in zip(TABS, layout["tabs"])
                            if rect.collidepoint(ev.pos)), None)
            if clicked is not None:
                if clicked != tab:
                    tab = clicked
                    auto_running = False
                    for slider in sliders.values():
                        slider.dragging = False
                    views = map_views(tab, layout, current_map)
                continue
            if layout["theme"].collidepoint(ev.pos):
                theme = "dark" if theme == "light" else "light"
                continue

        if tab == "builder":                 # restul evenimentelor merg la editor
            builder.handle_event(ev, layout["body"])
            continue

        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            alive = False
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:    # 1 = click stânga
            if layout["btn_map"].collidepoint(ev.pos):
                maps.next()
                start = finish = None
                points_path = maps.path()
                # harta și transformările se recalculează imediat, ca restul cadrului
                # (și simularea) să nu mai lucreze cu harta veche
                current_map = maps.current()
                views = map_views(tab, layout, current_map)
            elif layout["btn_point"].collidepoint(ev.pos):
                point_mode = "finish" if point_mode == "start" else "start"
            elif layout["btn_step"].collidepoint(ev.pos):
                step_requested = True
            elif layout["btn_auto"].collidepoint(ev.pos):
                if auto_running:
                    auto_running = False           # al doilea click pune pauză
                elif not all(sims[name].finished for name in ACTIVE_SIMS[tab]):
                    auto_running = True
                    last_auto_step = now - AUTO_STEP_MS   # primul pas imediat
            else:
                for view in views.values():
                    if view.screen_rect().collidepoint(ev.pos):
                        point = view.to_map(*ev.pos)
                        which = "startul" if point_mode == "start" else "finishul"
                        if maps.on_obstacle(point):
                            notice = (f"Nu poti pune {which} pe un obstacol", now + NOTICE_MS)
                        elif point_mode == "start":
                            start = point
                        else:
                            finish = point
                        break

        # doar sliderele tabului curent ascultă evenimente
        for key, rect in slider_rects(tab, layout).items():
            sliders[key].handle(ev, rect)

    # 3. logică: orice schimbare de parametri pornește o simulare nouă
    active = ACTIVE_SIMS[tab]
    if tab != "builder":
        map_data = None if isinstance(current_map, str) else current_map
        for name, sim in sims.items():
            params = SimParams(name, maps.name(), start, finish, sliders["slider_x"].value,
                               sliders["slider_y"].value, sliders["slider_depth"].value)
            if params.key() != sim.key:
                sim.reset(params, map_data)
                if name in active:
                    auto_running = False

        if step_requested:
            for name in active:
                sims[name].step()
        if auto_running and now - last_auto_step >= AUTO_STEP_MS:
            last_auto_step = now
            progressed = [sims[name].step() for name in active]
            if not any(progressed) or all(sims[name].finished for name in active):
                auto_running = False               # AUTO se oprește singur la final

    # 4. desenare
    colors = THEMES[theme]
    screen.fill(colors["bg"])
    tab_rect = layout["tabs"][0]
    tab_font = uniform_font([label for _, label in TABS], int(tab_rect.w * 0.9), tab_rect.h // 2)
    for (name, label), rect in zip(TABS, layout["tabs"]):
        draw_button(screen, rect, label, name == tab, border, colors, tab_font)
    draw_theme_button(screen, layout["theme"], theme, border, colors)

    if tab == "builder":
        builder.draw(screen, layout["body"], colors, border)
    else:
        # ce arată fiecare pătrat: (titlu, mesaj, simularea desenată peste hartă)
        hint = f"Click pe harta = {'Start' if point_mode == 'start' else 'Finish'}"
        if tab == "compare":
            panels = {"map": ("Omogen", sims["grid"].message, sims["grid"]),
                      "panel": ("Arbore", sims["tree"].message, sims["tree"])}
        else:
            panels = {"map": ("Harta", hint, sims[tab])}

        for key, (title, status, sim) in panels.items():
            content = draw_panel(screen, layout[key], title, border, colors, size, status)
            if key not in views:
                draw_centered_text(screen, content, current_map, colors, size)
                continue
            view = views[key]
            draw_map(screen, current_map, view, border, colors)
            draw_cells_overlay(screen, view, sim.current_cells(), sim.cell_codes(), colors)
            draw_marker(screen, view, start, "S", START, size)
            draw_marker(screen, view, finish, "F", FINISH, size)

        # dreapta, în taburile cu o singură metodă: matricea sau graful frunzelor libere
        if tab == "grid":
            sim = sims["grid"]
            content = draw_panel(screen, layout["panel"], "Matrice", border, colors, size, sim.message)
            if sim.decomp is not None:
                draw_matrix(screen, content, sim.decomp, sim.cell_codes(), colors)
        elif tab == "tree":
            sim = sims["tree"]
            content = draw_panel(screen, layout["panel"], "Graf", border, colors, size, sim.message)
            if views:
                graph = sim.decomp.graph if sim.decomp is not None else {}
                path = sim.state.path if sim.state is not None else None
                draw_leaf_graph(screen, content, current_map.bounds, sim.current_cells(),
                                graph, sim.cell_codes(), path, colors)

        draw_button(screen, layout["btn_map"], f"Harta: {maps.name()}", False, border, colors)
        draw_button(screen, layout["btn_point"], "Start" if point_mode == "start" else "Finish",
                    False, border, colors)
        draw_button(screen, layout["btn_step"], "Step", False, border, colors)
        draw_button(screen, layout["btn_auto"], "AUTO", auto_running, border, colors)

        if tab == "compare":
            pygame.draw.rect(screen, colors["active"], layout["cmp_frame"], border)
            draw_stats_table(screen, layout["cmp_stats"], ("", "Omogen", "Arbore"),
                             comparison_rows(sims["grid"].stats(), sims["tree"].stats()),
                             border, colors)
        else:
            pygame.draw.rect(screen, colors["active"], layout["sliders"], border)   # rama sliderelor
        for key, rect in slider_rects(tab, layout).items():
            sliders[key].draw(screen, rect, border, colors)

        if now < notice[1]:
            draw_notice(screen, (w // 2, layout["map"].bottom - size * 2), notice[0], size, colors)

    # 5. afișare, abia după ce s-a desenat tot
    pygame.display.flip()
    clock.tick(60)        # limitează la ~60 FPS, altfel ține un core la 100%

pygame.quit()
