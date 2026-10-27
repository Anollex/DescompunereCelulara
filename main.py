"""Punctul de intrare: fereastra, starea interfeței și bucla principală.

Calculul propriu-zis (descompunere, căutare) stă în simulation.py și modulele lui;
aici doar se citesc intrările utilizatorului și se desenează.
"""
import warnings

import pygame

from config import AUTO_STEP_MS, CURVE_SAMPLES, MAPS_DIR, MIN_SIZE, THEMES
from layout import make_layout
from map_view import MapView, draw_map
from model import FINISH, START
from render import draw_cells_overlay, draw_leaf_graph, draw_marker, draw_matrix
from simulation import SimParams, Simulation
from svg_loader import list_maps, load_map
from widgets import Slider, draw_button, draw_centered_text, draw_panel, draw_theme_button


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
        self.files = list_maps(folder)
        self.index = 0
        self._cache = {}          # cale -> MapData sau mesaj de eroare (str)

    def next(self):
        if self.files:
            self.index = (self.index + 1) % len(self.files)

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


pygame.init()
screen = pygame.display.set_mode(MIN_SIZE, pygame.RESIZABLE)
set_minimum_window_size(MIN_SIZE)
pygame.display.set_caption("Descompunere celulara")
clock = pygame.time.Clock()

alive = True
mode = "grid"          # "grid" = metoda omogenă, "tree" = metoda arborelui
theme = "light"        # "light" / "dark"
maps = MapLibrary(MAPS_DIR)
point_mode = "start"   # ce punct pui la click pe hartă: "start" / "finish"
start = None           # punctele, în coordonate de HARTĂ
finish = None
auto_running = False
last_auto_step = 0     # momentul (ms) ultimului pas făcut de AUTO
sim = Simulation()

# create o singură dată, ca să-și păstreze valoarea când schimbi tabul
sliders = {
    "slider_x":     Slider("Celule X", 5, 20, 10),
    "slider_y":     Slider("Celule Y", 5, 20, 10),
    "slider_depth": Slider("Adancime", 2, 8, 4),
}
SLIDERS_BY_MODE = {"grid": ["slider_x", "slider_y"], "tree": ["slider_depth"]}

while alive:
    # 1. dimensiuni calculate din fereastră și harta curentă, înainte de evenimente
    w, h = screen.get_size()
    layout = make_layout(w, h)
    border = layout["border"]
    size = layout["label_size"]
    now = pygame.time.get_ticks()

    current_map = maps.current()      # MapData, sau un mesaj de eroare (str)
    map_area = layout["map"].inflate(-2 * layout["pad"], -2 * layout["pad"])
    view = None if isinstance(current_map, str) else MapView(current_map.bounds, map_area)

    # 2. evenimente
    step_requested = False
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            alive = False
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            alive = False
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:    # 1 = click stânga
            if layout["tab_grid"].collidepoint(ev.pos):
                mode = "grid"
            elif layout["tab_tree"].collidepoint(ev.pos):
                mode = "tree"
            elif layout["theme"].collidepoint(ev.pos):
                theme = "dark" if theme == "light" else "light"
            elif layout["btn_map"].collidepoint(ev.pos):
                maps.next()
                start = finish = None              # punctele hărții vechi nu mai au sens
            elif layout["btn_point"].collidepoint(ev.pos):
                point_mode = "finish" if point_mode == "start" else "start"
            elif layout["btn_step"].collidepoint(ev.pos):
                step_requested = True
            elif layout["btn_auto"].collidepoint(ev.pos):
                if auto_running:
                    auto_running = False           # al doilea click pune pauză
                elif not sim.finished:
                    auto_running = True
                    last_auto_step = now - AUTO_STEP_MS   # primul pas imediat
            elif view is not None and view.screen_rect().collidepoint(ev.pos):
                point = view.to_map(*ev.pos)
                if point_mode == "start":
                    start = point
                else:
                    finish = point

        # doar sliderele modului curent ascultă evenimente
        for key in SLIDERS_BY_MODE[mode]:
            sliders[key].handle(ev, layout[key])

    # 3. logică: orice schimbare de parametri pornește o simulare nouă
    params = SimParams(mode, maps.name(), start, finish, sliders["slider_x"].value,
                       sliders["slider_y"].value, sliders["slider_depth"].value)
    if params.key() != sim.key:
        sim.reset(params, None if view is None else current_map)
        auto_running = False

    if step_requested:
        sim.step()
    if auto_running and now - last_auto_step >= AUTO_STEP_MS:
        last_auto_step = now
        if not sim.step() or sim.finished:
            auto_running = False                   # AUTO se oprește singur la final

    # 4. desenare
    colors = THEMES[theme]
    screen.fill(colors["bg"])
    draw_button(screen, layout["tab_grid"], "Metoda Omogena", mode == "grid", border, colors)
    draw_button(screen, layout["tab_tree"], "Metoda Arborelui", mode == "tree", border, colors)
    draw_theme_button(screen, layout["theme"], theme, border, colors)

    # stânga: harta, celulele peste ea, punctele
    pygame.draw.rect(screen, colors["fg"], layout["map"], border)
    codes = sim.cell_codes()
    if view is None:
        draw_centered_text(screen, map_area, current_map, colors, size)
    else:
        draw_map(screen, current_map, view, border, colors)
        draw_cells_overlay(screen, view, sim.current_cells(), codes, colors)
        draw_marker(screen, view, start, "S", START, size)
        draw_marker(screen, view, finish, "F", FINISH, size)

    # dreapta: matricea (omogen) sau graful frunzelor libere (arbore)
    if mode == "grid":
        content = draw_panel(screen, layout["panel"], f"Matrice | {sim.message}", border, colors, size)
        if sim.decomp is not None:
            draw_matrix(screen, content, sim.decomp, codes, colors)
    else:
        content = draw_panel(screen, layout["panel"], f"Graf | {sim.message}", border, colors, size)
        if view is not None:
            graph = sim.decomp.graph if sim.decomp is not None else {}
            path = sim.state.path if sim.state is not None else None
            draw_leaf_graph(screen, content, current_map.bounds, sim.current_cells(),
                            graph, codes, path, colors)

    draw_button(screen, layout["btn_map"], f"Harta: {maps.name()}", False, border, colors)
    draw_button(screen, layout["btn_point"], "Start" if point_mode == "start" else "Finish",
                False, border, colors)
    draw_button(screen, layout["btn_step"], "Step", False, border, colors)
    draw_button(screen, layout["btn_auto"], "AUTO", auto_running, border, colors)

    pygame.draw.rect(screen, colors["active"], layout["sliders"], border)   # rama sliderelor
    for key in SLIDERS_BY_MODE[mode]:
        sliders[key].draw(screen, layout[key], border, colors)

    # 5. afișare, abia după ce s-a desenat tot
    pygame.display.flip()
    clock.tick(60)        # limitează la ~60 FPS, altfel ține un core la 100%

pygame.quit()
