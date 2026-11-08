"""Visual SVG map builder used by the simulation application."""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, pi, sin
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pygame

from config import MAPS_DIR, THEMES
from widgets import draw_button, draw_centered_text, draw_theme_button, fit_font

LOGICAL_SIZE = (1000.0, 1000.0)
PALETTE = ("rectangle", "triangle", "circle")
LABELS = {"rectangle": "Rectangle", "triangle": "Triangle", "circle": "Circle"}


@dataclass
class PlacedShape:
    kind: str
    cx: float
    cy: float
    width: float = 150.0
    height: float = 100.0
    angle: float = 0.0
    locked: bool = False

    def points(self):
        if self.kind == "triangle":
            base = [(-0.5, 0.5), (0.5, 0.5), (0.0, -0.5)]
        elif self.kind == "circle":
            base = [(cos(2 * pi * i / 32), sin(2 * pi * i / 32)) for i in range(32)]
            diameter = min(self.width, self.height)
            base = [(x * diameter / (2 * self.width), y * diameter / (2 * self.height))
                    for x, y in base]
        else:
            base = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
        angle = self.angle * pi / 180.0
        ca, sa = cos(angle), sin(angle)
        return [
            (
                self.cx + x * self.width * ca - y * self.height * sa,
                self.cy + x * self.width * sa + y * self.height * ca,
            )
            for x, y in base
        ]

    def bounds(self):
        points = self.points()
        return (
            min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points), max(y for _, y in points),
        )


def _safe_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    cleaned = cleaned.strip("._")
    if not cleaned:
        raise ValueError("Map name cannot be empty")
    return cleaned


def save_svg(shapes, folder=MAPS_DIR, name="new_map"):
    """Write transformed polygons so the existing SVG loader can read them."""
    filename = _safe_name(name)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{filename}.svg"
    suffix = 2
    while path.exists():
        path = folder / f"{filename}_{suffix}.svg"
        suffix += 1
    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "viewBox": f"0 0 {LOGICAL_SIZE[0]:g} {LOGICAL_SIZE[1]:g}",
    })
    for shape in shapes:
        points = " ".join(f"{x:.4f},{y:.4f}" for x, y in shape.points())
        ET.SubElement(root, "polygon", {"points": points})
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


class MapBuilder:
    """State and rendering for a separate Pygame window."""

    def __init__(self, on_saved=None):
        self.window = None
        self.shapes = []
        self.selected = None
        self.dragging = False
        self.drag_offset = (0.0, 0.0)
        self.transform = None
        self.pending_palette = None
        self.theme = "light"
        self.map_name = "new_map"
        self.status = "Click a shape or drag it to the canvas."
        self.on_saved = on_saved
        self.active_property = None
        self.property_text = {}
        self.property_rects = {}
        self.property_select_all = False
        self.save_dialog = False
        self.save_name_text = ""
        self.save_name_select_all = False

    @property
    def open(self):
        return self.window is not None

    def show(self):
        if self.window is None:
            self.window = pygame.Window("Map Builder", size=(1100, 760), resizable=True)
            self.window.maximize()
        else:
            self.window.focus()

    def close(self):
        if self.window is not None:
            self.window.destroy()
            self.window = None

    def _layout(self, size):
        w, h = size
        sidebar_width = 360
        palette = pygame.Rect(15, 60, sidebar_width, max(160, h - 420))
        properties = pygame.Rect(15, palette.bottom + 15, sidebar_width, max(180, h - palette.bottom - 30))
        canvas_area = pygame.Rect(395, 60, max(100, w - 410), max(100, h - 125))
        side = max(100, min(canvas_area.w, canvas_area.h))
        canvas = pygame.Rect(canvas_area.x, canvas_area.y, side, side)
        canvas.center = canvas_area.center
        buttons = {
            "save": pygame.Rect(15, 12, 110, 34),
            "theme": pygame.Rect(135, 12, 34, 34),
        }
        return palette, properties, canvas, buttons

    def _to_screen(self, point, canvas):
        sx = canvas.x + point[0] * canvas.w / LOGICAL_SIZE[0]
        sy = canvas.y + point[1] * canvas.h / LOGICAL_SIZE[1]
        return round(sx), round(sy)

    def _to_map(self, point, canvas):
        return (
            (point[0] - canvas.x) * LOGICAL_SIZE[0] / canvas.w,
            (point[1] - canvas.y) * LOGICAL_SIZE[1] / canvas.h,
        )

    def _screen_polygon(self, shape, canvas):
        return [self._to_screen(point, canvas) for point in shape.points()]

    @staticmethod
    def _rotate_local(shape, x, y):
        angle = shape.angle * pi / 180.0
        ca, sa = cos(angle), sin(angle)
        return (shape.cx + x * ca - y * sa, shape.cy + x * sa + y * ca)

    @staticmethod
    def _unrotate(shape, x, y):
        angle = shape.angle * pi / 180.0
        ca, sa = cos(angle), sin(angle)
        dx, dy = x - shape.cx, y - shape.cy
        return (dx * ca + dy * sa, -dx * sa + dy * ca)

    def _selection_handles(self, shape, canvas):
        half_w, half_h = shape.width / 2, shape.height / 2
        local_corners = [
            (-half_w, -half_h), (half_w, -half_h),
            (half_w, half_h), (-half_w, half_h),
        ]
        corners = [self._to_screen(self._rotate_local(shape, *corner), canvas)
                   for corner in local_corners]
        top_mid = self._to_screen(self._rotate_local(shape, 0, -half_h), canvas)
        rotate_tip = self._to_screen(
            self._rotate_local(shape, 0, -half_h - max(35, shape.height * 0.22)), canvas)
        return corners, top_mid, rotate_tip

    def _hit_transform_handle(self, point, canvas):
        if self.selected is None or self.selected >= len(self.shapes):
            return None
        shape = self.shapes[self.selected]
        corners, _, rotate_tip = self._selection_handles(shape, canvas)
        mouse = pygame.Vector2(point)
        if mouse.distance_to(rotate_tip) <= 12:
            return "rotate"
        for index, corner in enumerate(corners):
            if mouse.distance_to(corner) <= 12:
                return ("scale", index)
        return None

    def _scale_from_corner(self, shape, corner_index, point, canvas):
        transform = self.transform
        if not isinstance(transform, dict):
            return
        map_point = self._to_map(point, canvas)
        initial_cx, initial_cy = transform["center"]
        angle = transform["angle"] * pi / 180.0
        ca, sa = cos(angle), sin(angle)
        dx, dy = map_point[0] - initial_cx, map_point[1] - initial_cy
        local_point = (dx * ca + dy * sa, -dx * sa + dy * ca)
        signs = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        sx, sy = signs[corner_index]
        initial_width = transform["width"]
        initial_height = transform["height"]
        opposite_x, opposite_y = -sx * initial_width / 2, -sy * initial_height / 2
        factor = max(
            abs(local_point[0]) / max(1, initial_width / 2),
            abs(local_point[1]) / max(1, initial_height / 2),
        )
        factor = max(0.15, factor)
        new_width = max(25.0, initial_width * factor)
        new_height = max(25.0, initial_height * factor)
        if shape.kind == "circle":
            new_width = new_height = max(new_width, new_height)
        anchor = (
            initial_cx + opposite_x * ca - opposite_y * sa,
            initial_cy + opposite_x * sa + opposite_y * ca,
        )
        new_opposite = (-sx * new_width / 2, -sy * new_height / 2)
        shape.width = new_width
        shape.height = new_height
        rotated_opposite = (
            shape.cx + new_opposite[0] * ca - new_opposite[1] * sa,
            shape.cy + new_opposite[0] * sa + new_opposite[1] * ca,
        )
        shape.cx += anchor[0] - rotated_opposite[0]
        shape.cy += anchor[1] - rotated_opposite[1]

    def _rotate_from_pointer(self, shape, point, canvas):
        x, y = self._to_map(point, canvas)
        shape.angle = degrees(atan2(y - shape.cy, x - shape.cx)) + 90

    def _hit_shape(self, point, canvas):
        x, y = self._to_map(point, canvas)
        for index in range(len(self.shapes) - 1, -1, -1):
            left, top, right, bottom = self.shapes[index].bounds()
            if left <= x <= right and top <= y <= bottom:
                return index
        return None

    def _property_values(self, shape):
        left, top, _, _ = shape.bounds()
        values = {
            "x": left, "y": top, "angle": shape.angle % 360,
        }
        if shape.kind == "rectangle":
            values.update(length=shape.width, width=shape.height)
        elif shape.kind == "circle":
            values["radius"] = min(shape.width, shape.height) / 2
        else:
            points = shape.points()
            for index in range(3):
                a = points[index]
                b = points[(index + 1) % 3]
                values[f"side{index + 1}"] = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        return values

    def _sync_property_text(self):
        if self.selected is None or self.selected >= len(self.shapes):
            self.property_text = {}
            self.active_property = None
            return
        values = self._property_values(self.shapes[self.selected])
        self.property_text = {key: f"{value:.2f}" for key, value in values.items()}

    def _property_rects_for(self, rect, shape):
        names = ["x", "y", "angle"]
        if shape.kind == "rectangle":
            names += ["length", "width"]
        elif shape.kind == "circle":
            names += ["radius"]
        row_h = max(28, min(38, (rect.h - 72) // len(names)))
        return {
            name: pygame.Rect(rect.x + 145, rect.y + 65 + index * row_h, rect.w - 155, row_h - 4)
            for index, name in enumerate(names)
        }

    @staticmethod
    def _save_dialog_rects(size):
        w, h = size
        dialog = pygame.Rect(0, 0, min(560, w - 40), 220)
        dialog.center = (w // 2, h // 2)
        return (
            dialog,
            pygame.Rect(dialog.x + 30, dialog.y + 70, dialog.w - 60, 42),
            pygame.Rect(dialog.right - 220, dialog.bottom - 58, 90, 36),
            pygame.Rect(dialog.right - 115, dialog.bottom - 58, 85, 36),
        )

    def _save_named_map(self):
        try:
            path = save_svg(self.shapes, name=self.save_name_text)
            self.map_name = path.stem
            self.status = f"Saved {path.name}."
            if self.on_saved:
                self.on_saved(path)
            self.save_dialog = False
            self.save_name_select_all = False
        except (OSError, ValueError) as exc:
            self.status = f"Save failed: {exc}"

    def _apply_property(self, name):
        if self.selected is None or self.selected >= len(self.shapes):
            return
        try:
            value = float(self.property_text[name])
        except (KeyError, ValueError):
            self._sync_property_text()
            return
        shape = self.shapes[self.selected]
        if name in ("x", "y"):
            left, top, _, _ = shape.bounds()
            if name == "x":
                shape.cx += value - left
            else:
                shape.cy += value - top
        elif name == "angle":
            shape.angle = value
        elif name in ("length", "width", "radius"):
            left, top, _, _ = shape.bounds()
            if name == "length":
                shape.width = max(25.0, value)
            elif name == "width":
                shape.height = max(25.0, value)
            else:
                diameter = max(25.0, value * 2)
                shape.width = shape.height = diameter
            new_left, new_top, _, _ = shape.bounds()
            shape.cx += left - new_left
            shape.cy += top - new_top
        self._sync_property_text()

    def _property_click(self, position, rect, shape):
        self.property_rects = self._property_rects_for(rect, shape)
        for name, field in self.property_rects.items():
            if field.collidepoint(position):
                if self.active_property and self.active_property != name:
                    self._apply_property(self.active_property)
                self.active_property = name
                self.property_select_all = True
                return True
        lock_rect = pygame.Rect(rect.x + 145, rect.y + 35, rect.w - 155, 25)
        if lock_rect.collidepoint(position):
            shape.locked = not shape.locked
            self._sync_property_text()
            return True
        delete_rect = pygame.Rect(rect.right - 110, rect.bottom - 42, 100, 32)
        if delete_rect.collidepoint(position):
            self._button_action("delete")
            return True
        return False

    def _place(self, kind, point, canvas):
        x, y = self._to_map(point, canvas)
        size = 125.0 if kind == "circle" else None
        shape = PlacedShape(kind, max(75, min(LOGICAL_SIZE[0] - 75, x)),
                            max(75, min(LOGICAL_SIZE[1] - 75, y)),
                            size or 150.0, size or 100.0)
        self.shapes.append(shape)
        self.selected = len(self.shapes) - 1
        self._sync_property_text()
        self.status = f"{LABELS[kind]} placed."

    def _button_action(self, name):
        if self.selected is None or self.selected >= len(self.shapes):
            return
        shape = self.shapes[self.selected]
        if name == "lock":
            shape.locked = not shape.locked
            self.status = "Position locked." if shape.locked else "Position unlocked."
        elif shape.locked:
            self.status = "Unlock this shape first."
        elif name == "rotate_left":
            shape.angle -= 15
        elif name == "rotate_right":
            shape.angle += 15
        elif name == "scale_up":
            shape.width *= 1.15
            shape.height *= 1.15
        elif name == "scale_down":
            shape.width = max(25, shape.width / 1.15)
            shape.height = max(25, shape.height / 1.15)
        elif name == "delete":
            self.shapes.pop(self.selected)
            self.selected = None
            self._sync_property_text()
            self.status = "Shape deleted."
        if self.active_property is None and self.selected is not None:
            self._sync_property_text()

    def handle_event(self, event):
        if self.window is None:
            return
        event_window = getattr(event, "window", None)
        if event_window is not None and getattr(event_window, "id", None) != self.window.id:
            return
        if event.type == pygame.WINDOWCLOSE:
            self.close()
            return
        surface = self.window.get_surface()
        palette, _, canvas, buttons = self._layout(surface.get_size())
        properties = self._layout(surface.get_size())[1]
        if self.save_dialog:
            dialog, field, save_rect, cancel_rect = self._save_dialog_rects(surface.get_size())
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if field.collidepoint(event.pos):
                    self.save_name_select_all = True
                elif save_rect.collidepoint(event.pos):
                    self._save_named_map()
                elif cancel_rect.collidepoint(event.pos):
                    self.save_dialog = False
                    self.save_name_select_all = False
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    self._save_named_map()
                elif event.key == pygame.K_ESCAPE:
                    self.save_dialog = False
                    self.save_name_select_all = False
                elif event.key == pygame.K_a and (getattr(event, "mod", 0) & pygame.KMOD_CTRL):
                    self.save_name_select_all = True
                elif event.key == pygame.K_BACKSPACE:
                    if self.save_name_select_all:
                        self.save_name_text = ""
                        self.save_name_select_all = False
                    else:
                        self.save_name_text = self.save_name_text[:-1]
                elif event.unicode and event.unicode not in "\r\n":
                    if self.save_name_select_all:
                        self.save_name_text = ""
                        self.save_name_select_all = False
                    self.save_name_text += event.unicode
                return
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.active_property is not None:
                self._apply_property(self.active_property)
                self.active_property = None
            if self.selected is not None and self.selected < len(self.shapes):
                if self._property_click(event.pos, properties, self.shapes[self.selected]):
                    return
            if buttons["save"].collidepoint(event.pos):
                self.save_name_text = self.map_name
                self.save_name_select_all = True
                self.save_dialog = True
                return
            if buttons["theme"].collidepoint(event.pos):
                self.theme = "dark" if self.theme == "light" else "light"
                return
            for i, kind in enumerate(PALETTE):
                item = pygame.Rect(palette.x + 20, palette.y + 35 + i * 125, palette.w - 40, 100)
                if item.collidepoint(event.pos):
                    self.pending_palette = kind
                    if canvas.collidepoint(event.pos):
                        self._place(kind, event.pos, canvas)
                    else:
                        self.status = f"Drag {LABELS[kind]} onto the canvas."
                    return
            if canvas.collidepoint(event.pos):
                handle = self._hit_transform_handle(event.pos, canvas)
                if handle and not self.shapes[self.selected].locked:
                    self.dragging = True
                    if isinstance(handle, tuple):
                        shape = self.shapes[self.selected]
                        self.transform = {
                            "kind": "scale",
                            "corner": handle[1],
                            "center": (shape.cx, shape.cy),
                            "width": shape.width,
                            "height": shape.height,
                            "angle": shape.angle,
                        }
                    else:
                        self.transform = handle
                    return
                index = self._hit_shape(event.pos, canvas)
                self.selected = index
                self._sync_property_text()
                if index is None:
                    self.status = "Nothing selected."
                elif not self.shapes[index].locked:
                    shape = self.shapes[index]
                    point = self._to_map(event.pos, canvas)
                    self.dragging = True
                    self.transform = None
                    self.drag_offset = (shape.cx - point[0], shape.cy - point[1])
        elif event.type == pygame.MOUSEMOTION and self.dragging and self.selected is not None:
            shape = self.shapes[self.selected]
            if not shape.locked:
                if self.transform == "rotate":
                    self._rotate_from_pointer(shape, event.pos, canvas)
                elif isinstance(self.transform, dict) and self.transform["kind"] == "scale":
                    self._scale_from_corner(shape, self.transform["corner"], event.pos, canvas)
                else:
                    point = self._to_map(event.pos, canvas)
                    shape.cx = max(0, min(LOGICAL_SIZE[0], point[0] + self.drag_offset[0]))
                    shape.cy = max(0, min(LOGICAL_SIZE[1], point[1] + self.drag_offset[1]))
                if self.active_property is None:
                    self._sync_property_text()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.pending_palette and canvas.collidepoint(event.pos):
                self._place(self.pending_palette, event.pos, canvas)
            self.pending_palette = None
            self.dragging = False
            self.transform = None
        elif event.type == pygame.KEYDOWN:
            if self.active_property is not None:
                if event.key == pygame.K_RETURN:
                    self._apply_property(self.active_property)
                    self.active_property = None
                    self.property_select_all = False
                elif event.key == pygame.K_a and (getattr(event, "mod", 0) & pygame.KMOD_CTRL):
                    self.property_select_all = True
                elif event.key == pygame.K_BACKSPACE:
                    if self.property_select_all:
                        self.property_text[self.active_property] = ""
                        self.property_select_all = False
                    else:
                        self.property_text[self.active_property] = self.property_text[self.active_property][:-1]
                elif event.key == pygame.K_ESCAPE:
                    self._sync_property_text()
                    self.property_select_all = False
                elif event.unicode and event.unicode in "0123456789.-":
                    if self.property_select_all:
                        self.property_text[self.active_property] = ""
                        self.property_select_all = False
                    self.property_text[self.active_property] += event.unicode
            elif event.key == pygame.K_DELETE:
                self._button_action("delete")
            elif event.key == pygame.K_ESCAPE:
                self.selected = None
                self._sync_property_text()

    def draw(self):
        if self.window is None:
            return
        surface = self.window.get_surface()
        colors = THEMES[self.theme]
        surface.fill(colors["bg"])
        palette, properties, canvas, buttons = self._layout(surface.get_size())
        draw_button(surface, buttons["save"], "Save Map", False, 2, colors)
        draw_theme_button(surface, buttons["theme"], self.theme, 2, colors)
        pygame.draw.rect(surface, colors["fg"], palette, 2)
        pygame.draw.rect(surface, colors["fg"], properties, 2)
        pygame.draw.rect(surface, colors["fg"], canvas, 2)
        draw_centered_text(surface, pygame.Rect(palette.x, palette.y + 5, palette.w, 25),
                           "Shapes", colors, 20)
        for i, kind in enumerate(PALETTE):
            item = pygame.Rect(palette.x + 20, palette.y + 35 + i * 125, palette.w - 40, 100)
            pygame.draw.rect(surface, colors["active"] if self.pending_palette == kind else colors["map_bg"], item)
            pygame.draw.rect(surface, colors["fg"], item, 1)
            center = item.center
            if kind == "rectangle":
                pygame.draw.rect(surface, colors["obstacle"], pygame.Rect(center[0] - 50, center[1] - 25, 100, 50), 3)
            elif kind == "triangle":
                pygame.draw.polygon(surface, colors["obstacle"], [(center[0], center[1] - 38),
                                   (center[0] - 45, center[1] + 35), (center[0] + 45, center[1] + 35)], 3)
            else:
                pygame.draw.circle(surface, colors["obstacle"], center, 35, 3)
            font = fit_font(LABELS[kind], item.w, 18)
            surface.blit(font.render(LABELS[kind], True, colors["fg"]),
                         (item.x + 6, item.bottom - 22))
        if self.active_property is None:
            self._sync_property_text()
        self._draw_properties(surface, properties, colors)
        surface.set_clip(canvas)
        for index, shape in enumerate(self.shapes):
            polygon = self._screen_polygon(shape, canvas)
            pygame.draw.polygon(surface, colors["obstacle"], polygon, 0)
            pygame.draw.polygon(surface, colors["fg"], polygon, 2)
            if index == self.selected:
                corners, top_mid, rotate_tip = self._selection_handles(shape, canvas)
                pygame.draw.line(surface, (40, 100, 220), top_mid, rotate_tip, 2)
                pygame.draw.lines(surface, (40, 100, 220), True, corners, 2)
                for corner in corners:
                    pygame.draw.rect(surface, (40, 100, 220), pygame.Rect(corner[0] - 5, corner[1] - 5, 10, 10))
                pygame.draw.circle(surface, (40, 100, 220), rotate_tip, 8)
        surface.set_clip(None)
        pygame.draw.rect(surface, colors["fg"], canvas, 2)
        draw_centered_text(surface, pygame.Rect(canvas.x, canvas.bottom + 5, canvas.w, 28),
                           self.status, colors, 16)
        if self.save_dialog:
            dialog, field, save_rect, cancel_rect = self._save_dialog_rects(surface.get_size())
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            surface.blit(overlay, (0, 0))
            pygame.draw.rect(surface, colors["map_bg"], dialog)
            pygame.draw.rect(surface, colors["fg"], dialog, 2)
            draw_centered_text(surface, pygame.Rect(dialog.x, dialog.y + 15, dialog.w, 32),
                               "Save Map", colors, 24)
            pygame.draw.rect(surface, colors["active"] if self.save_name_select_all else colors["bg"], field)
            pygame.draw.rect(surface, colors["fg"], field, 2)
            name_font = fit_font(self.save_name_text, field.w - 16, 22)
            surface.blit(name_font.render(self.save_name_text, True, colors["fg"]),
                         (field.x + 8, field.y + 8))
            draw_button(surface, save_rect, "Save", False, 2, colors)
            draw_button(surface, cancel_rect, "Cancel", False, 2, colors)
        self.window.flip()

    def _draw_properties(self, surface, rect, colors):
        """Display dimensions and transforms for the currently selected shape."""
        draw_centered_text(
            surface, pygame.Rect(rect.x, rect.y + 5, rect.w, 24),
            "Properties", colors, 18,
        )
        if self.selected is None or self.selected >= len(self.shapes):
            draw_centered_text(
                surface, pygame.Rect(rect.x + 5, rect.y + 38, rect.w - 10, rect.h - 43),
                "No shape selected", colors, 14,
            )
            return

        shape = self.shapes[self.selected]
        self.property_rects = self._property_rects_for(rect, shape)
        left, top, right, bottom = shape.bounds()
        lines = [
            ("Position X", "x"), ("Position Y", "y"), ("Angle", "angle"),
        ]
        if shape.kind == "rectangle":
            lines.extend((("Length", "length"), ("Width", "width")))
        elif shape.kind == "circle":
            lines.append(("Radius", "radius"))
        font = fit_font("Position X", 95, 18)
        for label, name in lines:
            field = self.property_rects[name]
            surface.blit(font.render(label, True, colors["fg"]), (rect.x + 6, field.y + 4))
            pygame.draw.rect(surface, colors["active"] if name == self.active_property else colors["map_bg"], field)
            pygame.draw.rect(surface, colors["fg"], field, 1)
            value_font = fit_font(self.property_text.get(name, ""), field.w - 8, 18)
            surface.blit(value_font.render(self.property_text.get(name, ""), True, colors["fg"]),
                         (field.x + 4, field.y + 4))
        lock_field = pygame.Rect(rect.x + 145, rect.y + 35, rect.w - 155, 25)
        pygame.draw.rect(surface, colors["active"], lock_field)
        pygame.draw.rect(surface, colors["fg"], lock_field, 1)
        lock_font = fit_font("Unlocked", lock_field.w - 8, 16)
        lock_text = "Locked" if shape.locked else "Unlocked"
        surface.blit(lock_font.render(lock_text, True, colors["fg"]), (lock_field.x + 4, lock_field.y + 3))
        lock_label_font = fit_font("Lock", 135, 20)
        surface.blit(lock_label_font.render("Lock", True, colors["fg"]), (rect.x + 6, lock_field.y + 3))
        delete_rect = pygame.Rect(rect.right - 110, rect.bottom - 42, 100, 32)
        draw_button(surface, delete_rect, "Delete", False, 2, colors)
