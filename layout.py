"""Calculul pozițiilor tuturor elementelor din fereastră, la fiecare cadru."""
import pygame

from config import BTN_FRAC, SLIDER_FRAC


def split_strip(x, y, w, h, n):
    """Împarte o bandă pe orizontală în n bucăți lipite."""
    rects = []
    for i in range(n):
        left = x + w * i // n
        right = x + w * (i + 1) // n     # calculezi capătul, nu lățimea
        rects.append(pygame.Rect(left, y, right - left, h))
    return rects


def split_with_gap(area, n, gap):
    """Împarte `area` pe orizontală în n bucăți, cu `gap` pixeli între ele."""
    usable = area.w - gap * (n - 1)
    rects = []
    for i in range(n):
        left = area.x + usable * i // n + gap * i
        right = area.x + usable * (i + 1) // n + gap * i
        rects.append(pygame.Rect(left, area.y, right - left, area.h))
    return rects


def stack_centered(area, width, heights, gap):
    """Așază pe verticală dreptunghiuri de înălțimi date, centrate ca grup în `area`."""
    total = sum(heights) + gap * (len(heights) - 1)
    x = area.centerx - width // 2
    y = area.centery - total // 2
    rows = []
    for hh in heights:
        rows.append(pygame.Rect(x, y, width, hh))
        y += hh + gap
    return rows


def make_layout(w, h):
    short = min(w, h)                      # dimensiunea mică decide grosimi și spații
    tab_h = max(20, min(h // 12, w // 14))
    pad = max(6, short // 60)

    # banda de sus: două taburi + butonul de temă în colț
    theme_btn = pygame.Rect(w - tab_h, 0, tab_h, tab_h)
    tab_grid, tab_tree = split_strip(0, 0, w - tab_h, tab_h, 2)

    # zona de sub taburi, cu margini
    body = pygame.Rect(pad, tab_h + pad, w - 2 * pad, h - tab_h - 2 * pad)

    # latura maximă: blocul trebuie să încapă și pe orizontală, și pe verticală
    side_by_w = (body.w - pad) // 2                                     # pătrat + gap + pătrat
    side_by_h = int((body.h - 2 * pad) / (1 + BTN_FRAC + SLIDER_FRAC))  # pătrat + butoane + slidere
    side = max(1, min(side_by_w, side_by_h))

    btn_h = max(1, int(side * BTN_FRAC))
    slider_h = max(1, int(side * SLIDER_FRAC))
    block_w = 2 * side + pad

    squares_row, buttons_row, sliders_row = stack_centered(
        body, block_w, [side, btn_h, slider_h], pad)

    map_rect = pygame.Rect(squares_row.left, squares_row.top, side, side)
    panel_rect = pygame.Rect(squares_row.right - side, squares_row.top, side, side)

    # rândul de butoane: 4 bucăți cu spații între ele
    btn_map, btn_point, btn_step, btn_auto = split_with_gap(buttons_row, 4, pad)

    # rândul de slidere: în interiorul ramei, două benzi (omogen) sau una centrată (arbore)
    inner = sliders_row.inflate(-2 * pad, -2 * pad)
    half_h = (inner.h - pad) // 2
    slider_x = pygame.Rect(inner.x, inner.y, inner.w, half_h)
    slider_y = pygame.Rect(inner.x, inner.bottom - half_h, inner.w, half_h)
    slider_depth = pygame.Rect(inner.x, 0, inner.w, half_h)
    slider_depth.centery = inner.centery

    return {
        "tab_grid": tab_grid, "tab_tree": tab_tree, "theme": theme_btn,
        "map": map_rect, "panel": panel_rect,
        "btn_map": btn_map, "btn_point": btn_point, "btn_step": btn_step, "btn_auto": btn_auto,
        "sliders": sliders_row,
        "slider_x": slider_x, "slider_y": slider_y, "slider_depth": slider_depth,
        "label_size": max(10, side // 20),     # aceeași mărime pentru toate titlurile de panou
        "border": max(1, short // 300),
        "pad": pad,
    }
