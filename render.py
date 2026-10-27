"""Desenarea simulării: celulele peste hartă, punctele start/finish, matricea și graful."""
import pygame

from map_view import MapView
from model import FINISH, FREE, FRONTIER, OCCUPIED, PATH, PENDING, START, VISITED
from widgets import get_font

# culoarea fiecărui cod (aceeași în ambele teme, ca să se recunoască ușor)
CODE_COLORS = {
    OCCUPIED: (215, 70, 70),
    FREE:     (90, 180, 100),
    VISITED:  (95, 145, 230),
    FRONTIER: (240, 190, 60),
    PATH:     (170, 90, 225),
    START:    (30, 190, 200),
    FINISH:   (235, 95, 165),
    PENDING:  (150, 150, 150),
}
# cât de opac e codul peste hartă (0-255): stările căutării ies mai tare în evidență
OVERLAY_ALPHA = {OCCUPIED: 110, FREE: 45, PENDING: 70,
                 VISITED: 120, FRONTIER: 170, PATH: 210, START: 230, FINISH: 230}
TEXT_ON_CODE = (20, 20, 20)


def draw_cells_overlay(surface, view, cells, codes, colors):
    """Celulele colorate semitransparent peste hartă, plus liniile dintre ele."""
    area = view.screen_rect()
    overlay = pygame.Surface(area.size, pygame.SRCALPHA)
    line = (*colors["fg"], 70)
    for cid, cell in cells.items():
        r = view.rect_to_screen(cell.x, cell.y, cell.w, cell.h).move(-area.x, -area.y)
        code = codes.get(cid, FREE)
        overlay.fill((*CODE_COLORS[code], OVERLAY_ALPHA[code]), r)
        if r.w >= 4 and r.h >= 4:                    # la celule minuscule liniile ar acoperi tot
            pygame.draw.rect(overlay, line, r, 1)
    surface.blit(overlay, area.topleft)


def draw_marker(surface, view, point, text, code, size):
    """Cerc cu literă (S / F) la un punct de hartă."""
    if point is None:
        return
    center = view.to_screen(*point)
    radius = max(7, size // 2)
    pygame.draw.circle(surface, CODE_COLORS[code], center, radius)
    pygame.draw.circle(surface, TEXT_ON_CODE, center, radius, 2)
    label = get_font(radius).render(text, True, TEXT_ON_CODE)
    surface.blit(label, label.get_rect(center=center))


_digit_cache = {}


def _digit(code, size):
    key = (code, size)
    if key not in _digit_cache:
        _digit_cache[key] = get_font(size).render(str(code), True, TEXT_ON_CODE)
    return _digit_cache[key]


def draw_matrix(surface, rect, decomp, codes, colors):
    """Matricea grilei: o căsuță pătrată per celulă, cu codul ei scris și colorat."""
    side = min(rect.w / decomp.cols, rect.h / decomp.rows)
    x0 = rect.centerx - side * decomp.cols / 2
    y0 = rect.centery - side * decomp.rows / 2
    digit_size = max(10, int(side * 0.5))
    for cid, cell in decomp.cells.items():
        left, top = round(x0 + cell.i * side), round(y0 + cell.j * side)
        r = pygame.Rect(left, top, round(x0 + (cell.i + 1) * side) - left,
                        round(y0 + (cell.j + 1) * side) - top)
        code = codes.get(cid, FREE)
        pygame.draw.rect(surface, CODE_COLORS[code], r)
        pygame.draw.rect(surface, colors["fg"], r, 1)
        if side >= 12:
            digit = _digit(code, digit_size)
            surface.blit(digit, digit.get_rect(center=r.center))


def draw_leaf_graph(surface, rect, bounds, cells, graph, codes, path, colors):
    """Graful frunzelor libere, desenat la pozițiile reale ale centrelor (alt MapView)."""
    view = MapView(bounds, rect)
    pygame.draw.rect(surface, colors["active"], view.screen_rect(), 1)

    # muchiile (fiecare o singură dată), apoi drumul peste ele, mai gros
    for a, neighbours in graph.items():
        pa = view.to_screen(*cells[a].center)
        for b, _ in neighbours:
            if a < b:
                pygame.draw.line(surface, colors["active"], pa, view.to_screen(*cells[b].center), 1)
    if path:
        points = [view.to_screen(*cells[c].center) for c in path]
        if len(points) > 1:
            pygame.draw.lines(surface, CODE_COLORS[PATH], False, points, 3)

    # nodurile: doar frunzele libere (acestea nu se mai împart niciodată)
    for cid, cell in cells.items():
        if not cell.free:
            continue
        radius = max(2, min(7, int(min(cell.w, cell.h) * view.scale * 0.2)))
        center = view.to_screen(*cell.center)
        pygame.draw.circle(surface, CODE_COLORS[codes.get(cid, FREE)], center, radius)
        pygame.draw.circle(surface, colors["fg"], center, radius, 1)
