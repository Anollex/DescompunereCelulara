"""Visual SVG map builder, shown as a tab of the simulation window.

The builder owns no window: main.py passes it the events and the rectangle it may
draw in. All shape data is kept in map coordinates (a 1000 x 1000 square).

Shape model: every obstacle is a box (centre, width, height, angle) plus an outline
described in the unit box [-0.5, 0.5]^2. Width and height are independent, so any
shape can be stretched; triangles and custom polygons also expose their vertices.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, pi, radians, sin, sqrt
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pygame

from config import MAPS_DIR
from widgets import draw_button, draw_centered_text, fit_font

LOGICAL_SIZE = (1000.0, 1000.0)
MIN_SIZE = 20.0                # smallest width / height a shape can be resized to
PALETTE = ("rectangle", "triangle", "circle", "custom")
LABELS = {"rectangle": "Rectangle", "triangle": "Triangle", "circle": "Circle / Oval",
          "custom": "Custom shape", "polygon": "Custom shape"}
EDITABLE = ("triangle", "polygon")          # kinds whose vertices can be moved
ELLIPSE_SEGMENTS = 48
TRIANGLE_VERTS = ((-0.5, 0.5), (0.5, 0.5), (0.0, -0.5))
EQUILATERAL = sqrt(3) / 2                   # height / side of an equilateral triangle
FREEHAND_STEP = 14.0                        # map units between two freehand points
HANDLE_COLOR = (40, 100, 220)
VERTEX_COLOR = (235, 130, 30)
HIT_RADIUS = 11                             # pixels around a handle that still grab it

FIELD_LABELS = {"x": "Position X", "y": "Position Y", "angle": "Angle",
                "width": "Width", "height": "Height", "rx": "Radius X", "ry": "Radius Y"}


@dataclass
class PlacedShape:
    kind: str                  # "rectangle", "triangle", "circle" (ellipse) or "polygon"
    cx: float
    cy: float
    width: float = 150.0
    height: float = 100.0
    angle: float = 0.0
    locked: bool = False
    verts: list | None = None  # outline in the unit box; only for triangle / polygon

    def __post_init__(self):
        if self.verts is None and self.kind == "triangle":
            self.verts = list(TRIANGLE_VERTS)
        if self.kind == "polygon" and (self.verts is None or len(self.verts) < 3):
            raise ValueError("A polygon needs at least 3 points")

    @classmethod
    def from_points(cls, points):
        """Custom polygon from map-coordinate points."""
        shape = cls("polygon", 0.0, 0.0, 1.0, 1.0, verts=[(0.0, 0.0)] * 3)
        shape.set_points(points)
        return shape

    # ---- coordinates: "local" = map units, relative to the centre, before rotation

    def to_world(self, x, y):
        angle = radians(self.angle)
        ca, sa = cos(angle), sin(angle)
        return (self.cx + x * ca - y * sa, self.cy + x * sa + y * ca)

    def to_local(self, x, y):
        angle = radians(self.angle)
        ca, sa = cos(angle), sin(angle)
        dx, dy = x - self.cx, y - self.cy
        return (dx * ca + dy * sa, -dx * sa + dy * ca)

    def _unit_outline(self):
        if self.verts is not None:
            return self.verts
        if self.kind == "circle":
            return [(0.5 * cos(2 * pi * i / ELLIPSE_SEGMENTS), 0.5 * sin(2 * pi * i / ELLIPSE_SEGMENTS))
                    for i in range(ELLIPSE_SEGMENTS)]
        return [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]

    def points(self):
        """Outline in map coordinates."""
        return [self.to_world(x * self.width, y * self.height) for x, y in self._unit_outline()]

    def bounds(self):
        points = self.points()
        return (
            min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points), max(y for _, y in points),
        )

    def contains(self, x, y):
        """Point-in-polygon test (ray casting) on the real outline."""
        points = self.points()
        inside = False
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
        return inside

    # ---- vertex editing

    def set_points(self, points):
        """Replace the outline with map-coordinate points; the box is refitted around them."""
        local = [self.to_local(x, y) for x, y in points]
        min_x, max_x = min(x for x, _ in local), max(x for x, _ in local)
        min_y, max_y = min(y for _, y in local), max(y for _, y in local)
        mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2
        width, height = max(1.0, max_x - min_x), max(1.0, max_y - min_y)
        self.cx, self.cy = self.to_world(mid_x, mid_y)
        self.width, self.height = width, height
        self.verts = [((x - mid_x) / width, (y - mid_y) / height) for x, y in local]

    def move_vertex(self, index, point):
        points = self.points()
        points[index] = point
        self.set_points(points)


def resize_shape(shape, initial, sx, sy, point, proportional=False):
    """Resize by dragging a handle to `point` (map coordinates).

    initial = (cx, cy, width, height, angle) when the drag started.
    (sx, sy) says which handle: each is -1, 0 or +1. A corner has both set and scales
    both axes; a side handle has one 0 and stretches a single axis. The opposite
    corner / side stays where it was.
    """
    cx0, cy0, w0, h0, angle = initial
    a = radians(angle)
    ca, sa = cos(a), sin(a)
    dx, dy = point[0] - cx0, point[1] - cy0
    local_x, local_y = dx * ca + dy * sa, -dx * sa + dy * ca
    anchor_x, anchor_y = -sx * w0 / 2, -sy * h0 / 2
    width = max(MIN_SIZE, (local_x - anchor_x) * sx) if sx else w0
    height = max(MIN_SIZE, (local_y - anchor_y) * sy) if sy else h0
    if proportional and sx and sy:
        factor = max(width / w0, height / h0)
        width, height = w0 * factor, h0 * factor
    mid_x, mid_y = anchor_x + sx * width / 2, anchor_y + sy * height / 2
    shape.width, shape.height = width, height
    shape.cx = cx0 + mid_x * ca - mid_y * sa
    shape.cy = cy0 + mid_x * sa + mid_y * ca


def polygon_area(points):
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def simplify_points(points, tolerance=5.0, keep_below=16):
    """Drop nearly collinear points from a long freehand stroke."""
    if len(points) <= keep_below:
        return points
    from shapely.geometry import LineString
    coords = list(LineString(points + points[:1]).simplify(tolerance).coords)[:-1]
    return [(float(x), float(y)) for x, y in coords] if len(coords) >= 3 else points


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


def _clamp_point(point):
    return (max(0.0, min(LOGICAL_SIZE[0], point[0])), max(0.0, min(LOGICAL_SIZE[1], point[1])))


class MapBuilder:
    """State, input handling and rendering of the builder tab."""

    def __init__(self, on_saved=None):
        self.shapes = []
        self.selected = None           # index into self.shapes
        self.editing = False           # vertex-edit mode for the selected shape
        self.drag = None               # ("move", dx, dy) / ("rotate",) / ("resize", sx, sy, initial) / ("vertex", i)
        self.pending = None            # palette shape waiting to be placed
        self.pending_pressed = False   # mouse still held since the palette click
        self.drawing = None            # list of points while drawing a custom shape
        self.freehand = False          # mouse held while drawing: add points along the way
        self.mouse = (0, 0)
        self.last_click = (None, 0)    # (shape index, time) for double-click detection
        self.clear_armed_until = 0
        self.map_name = "new_map"
        self.status = "Pick a shape on the left, then click on the canvas."
        self.on_saved = on_saved
        self.active_property = None
        self.property_text = {}
        self.property_select_all = False
        self.save_dialog = False
        self.save_name_text = ""
        self.save_name_select_all = False

    # ------------------------------------------------------------------ layout

    def _layout(self, rect):
        unit = max(12, min(rect.h // 40, rect.w // 70))        # base text size
        pad = max(6, unit // 2)
        side_w = max(220, min(int(rect.w * 0.27), 400))
        btn_h = int(unit * 2.4)
        half = (side_w - pad) // 2
        save = pygame.Rect(rect.x, rect.y, half, btn_h)
        clear = pygame.Rect(rect.x + side_w - half, rect.y, half, btn_h)
        palette_h = int((rect.h - btn_h - 2 * pad) * 0.36)
        palette = pygame.Rect(rect.x, save.bottom + pad, side_w, palette_h)
        properties = pygame.Rect(rect.x, palette.bottom + pad, side_w, rect.bottom - palette.bottom - pad)

        status_h = int(unit * 1.8)
        area = pygame.Rect(rect.x + side_w + pad, rect.y, rect.right - rect.x - side_w - pad,
                           rect.h - status_h)
        side = max(50, min(area.w, area.h))
        canvas = pygame.Rect(0, 0, side, side)
        canvas.center = area.center
        status = pygame.Rect(area.x, area.bottom, area.w, status_h)

        # palette: title + 2 x 2 grid of shapes
        title_h = int(unit * 1.8)
        grid = pygame.Rect(palette.x + pad, palette.y + title_h, palette.w - 2 * pad,
                           palette.h - title_h - pad)
        cell_w, cell_h = (grid.w - pad) // 2, (grid.h - pad) // 2
        items = {}
        for i, kind in enumerate(PALETTE):
            items[kind] = pygame.Rect(grid.x + (i % 2) * (cell_w + pad),
                                      grid.y + (i // 2) * (cell_h + pad), cell_w, cell_h)
        return {"unit": unit, "pad": pad, "save": save, "clear": clear, "palette": palette,
                "items": items, "properties": properties, "canvas": canvas, "status": status}

    def _property_layout(self, lay, shape):
        rect, unit, pad = lay["properties"], lay["unit"], lay["pad"]
        names = ["x", "y", "angle"] + (["rx", "ry"] if shape.kind == "circle" else ["width", "height"])
        title_h = int(unit * 1.8)
        btn_h = int(unit * 2.2)
        room = rect.h - title_h - btn_h - 3 * pad
        row_h = max(16, min(int(unit * 2.2), room // (len(names) + 1)))
        label_w = int(rect.w * 0.42)
        x, w = rect.x + label_w, rect.w - label_w - pad
        lock = pygame.Rect(x, rect.y + title_h, w, row_h - 4)
        fields = {name: pygame.Rect(x, rect.y + title_h + (i + 1) * row_h, w, row_h - 4)
                  for i, name in enumerate(names)}
        half = (rect.w - 3 * pad) // 2
        y = rect.bottom - pad - btn_h
        edit = pygame.Rect(rect.x + pad, y, half, btn_h) if shape.kind in EDITABLE else None
        delete = pygame.Rect(rect.right - pad - half, y, half, btn_h)
        return {"lock": lock, "fields": fields, "edit": edit, "delete": delete}

    @staticmethod
    def _save_dialog_rects(rect, unit):
        dialog = pygame.Rect(0, 0, min(unit * 32, rect.w - 40), unit * 12)
        dialog.center = rect.center
        btn_w, btn_h = unit * 6, int(unit * 2.2)
        return (
            dialog,
            pygame.Rect(dialog.x + unit * 2, dialog.y + unit * 4, dialog.w - unit * 4, int(unit * 2.4)),
            pygame.Rect(dialog.right - 2 * btn_w - unit * 3, dialog.bottom - btn_h - unit, btn_w, btn_h),
            pygame.Rect(dialog.right - btn_w - unit * 2, dialog.bottom - btn_h - unit, btn_w, btn_h),
        )

    # ------------------------------------------------------------------ coordinates and hit tests

    @staticmethod
    def _to_screen(point, canvas):
        return (round(canvas.x + point[0] * canvas.w / LOGICAL_SIZE[0]),
                round(canvas.y + point[1] * canvas.h / LOGICAL_SIZE[1]))

    @staticmethod
    def _to_map(point, canvas):
        return ((point[0] - canvas.x) * LOGICAL_SIZE[0] / canvas.w,
                (point[1] - canvas.y) * LOGICAL_SIZE[1] / canvas.h)

    def _selected_shape(self):
        if self.selected is None or self.selected >= len(self.shapes):
            return None
        return self.shapes[self.selected]

    def _handles(self, shape, canvas):
        """Resize handles as (sx, sy, screen position), plus the rotate handle."""
        half_w, half_h = shape.width / 2, shape.height / 2
        signs = [(-1, -1), (1, -1), (1, 1), (-1, 1), (0, -1), (1, 0), (0, 1), (-1, 0)]
        handles = [(sx, sy, self._to_screen(shape.to_world(sx * half_w, sy * half_h), canvas))
                   for sx, sy in signs]
        stem = 32 * LOGICAL_SIZE[1] / canvas.h            # constant length on screen
        top_mid = self._to_screen(shape.to_world(0, -half_h), canvas)
        rotate_tip = self._to_screen(shape.to_world(0, -half_h - stem), canvas)
        return handles, top_mid, rotate_tip

    def _hit_handle(self, position, canvas, shape):
        handles, _, rotate_tip = self._handles(shape, canvas)
        if hypot(position[0] - rotate_tip[0], position[1] - rotate_tip[1]) <= HIT_RADIUS:
            return "rotate"
        for sx, sy, spot in handles:              # corners come first in the list
            if hypot(position[0] - spot[0], position[1] - spot[1]) <= HIT_RADIUS:
                return (sx, sy)
        return None

    def _hit_vertex(self, position, canvas, shape):
        for index, point in enumerate(shape.points()):
            spot = self._to_screen(point, canvas)
            if hypot(position[0] - spot[0], position[1] - spot[1]) <= HIT_RADIUS:
                return index
        return None

    def _edge_midpoints(self, shape, canvas):
        points = shape.points()
        return [self._to_screen(((x1 + x2) / 2, (y1 + y2) / 2), canvas)
                for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])]

    def _hit_midpoint(self, position, canvas, shape):
        for index, spot in enumerate(self._edge_midpoints(shape, canvas)):
            if hypot(position[0] - spot[0], position[1] - spot[1]) <= HIT_RADIUS - 2:
                return index
        return None

    def _hit_shape(self, point):
        for index in range(len(self.shapes) - 1, -1, -1):      # topmost first
            if self.shapes[index].contains(*point):
                return index
        return None

    # ------------------------------------------------------------------ properties panel

    def _property_values(self, shape):
        left, top, _, _ = shape.bounds()
        values = {"x": left, "y": top, "angle": shape.angle % 360}
        if shape.kind == "circle":
            values.update(rx=shape.width / 2, ry=shape.height / 2)
        else:
            values.update(width=shape.width, height=shape.height)
        return values

    def _sync_property_text(self):
        shape = self._selected_shape()
        if shape is None:
            self.property_text = {}
            self.active_property = None
            return
        self.property_text = {key: f"{value:.2f}" for key, value in self._property_values(shape).items()}

    def _apply_property(self, name):
        shape = self._selected_shape()
        if shape is None:
            return
        try:
            value = float(self.property_text[name])
        except (KeyError, ValueError):
            self._sync_property_text()
            return
        if shape.locked:
            self.status = "Unlock this shape first."
        elif name in ("x", "y"):
            left, top, _, _ = shape.bounds()
            if name == "x":
                shape.cx += value - left
            else:
                shape.cy += value - top
        elif name == "angle":
            shape.angle = value
        else:
            left, top, _, _ = shape.bounds()
            scale = 2 if name in ("rx", "ry") else 1
            if name in ("width", "rx"):
                shape.width = max(MIN_SIZE, value * scale)
            else:
                shape.height = max(MIN_SIZE, value * scale)
            new_left, new_top, _, _ = shape.bounds()       # keep the top-left corner in place
            shape.cx += left - new_left
            shape.cy += top - new_top
        self._sync_property_text()

    def _property_click(self, position, lay, shape):
        rows = self._property_layout(lay, shape)
        for name, field in rows["fields"].items():
            if field.collidepoint(position):
                self.active_property = name
                self.property_select_all = True
                return True
        if rows["lock"].collidepoint(position):
            shape.locked = not shape.locked
            if shape.locked:
                self.editing = False
            self.status = "Shape locked." if shape.locked else "Shape unlocked."
            return True
        if rows["edit"] is not None and rows["edit"].collidepoint(position):
            self._toggle_editing()
            return True
        if rows["delete"].collidepoint(position):
            self._delete_selected()
            return True
        return False

    def _toggle_editing(self):
        shape = self._selected_shape()
        if shape is None or shape.kind not in EDITABLE:
            return
        if shape.locked:
            self.status = "Unlock this shape first."
            return
        self.editing = not self.editing
        if not self.editing:
            self.status = "Point editing finished."
        elif shape.kind == "polygon":
            self.status = "Drag a point. Drag a small marker to add a point, right-click a point to remove it."
        else:
            self.status = "Drag a corner of the triangle to move it."

    def _delete_selected(self):
        if self._selected_shape() is None:
            return
        self.shapes.pop(self.selected)
        self.selected = None
        self.editing = False
        self.drag = None
        self._sync_property_text()
        self.status = "Shape deleted."

    # ------------------------------------------------------------------ placing and drawing

    def _place(self, kind, point):
        if kind == "triangle":
            width, height = 150.0, 150.0 * EQUILATERAL          # equilateral base shape
        elif kind == "circle":
            width = height = 125.0
        else:
            width, height = 150.0, 100.0
        x = max(width / 2, min(LOGICAL_SIZE[0] - width / 2, point[0]))
        y = max(height / 2, min(LOGICAL_SIZE[1] - height / 2, point[1]))
        self.shapes.append(PlacedShape(kind, x, y, width, height))
        self.selected = len(self.shapes) - 1
        self.editing = False
        self._sync_property_text()
        self.status = f"{LABELS[kind]} placed. Drag the handles to resize, stretch or rotate it."

    def _arm(self, kind):
        """A palette entry was pressed."""
        self.editing = False
        self.drag = None
        if kind == "custom":
            self.pending = None
            self.drawing = []
            self.selected = None
            self._sync_property_text()
            self.status = "Click to add points or hold and drag to draw. Enter or a click on the first point closes the shape."
        else:
            self.drawing = None
            self.pending = kind
            self.pending_pressed = True
            self.status = f"Click or drop on the canvas to place the {LABELS[kind].lower()}."

    def _draw_click(self, position, point, canvas):
        points = self.drawing
        if points:
            first, last = self._to_screen(points[0], canvas), self._to_screen(points[-1], canvas)
            near_first = hypot(position[0] - first[0], position[1] - first[1]) <= HIT_RADIUS
            near_last = hypot(position[0] - last[0], position[1] - last[1]) <= 6
            if len(points) >= 3 and (near_first or near_last):      # closing click or double click
                self._finish_drawing()
                return
            if near_last:
                return
        points.append(point)
        self.freehand = True

    def _finish_drawing(self):
        points = simplify_points(self.drawing or [])
        if len(points) < 3 or polygon_area(points) < 100.0:
            self.status = "A custom shape needs at least 3 points that are not on one line."
            return
        self.shapes.append(PlacedShape.from_points(points))
        self.selected = len(self.shapes) - 1
        self.drawing = None
        self.freehand = False
        self._sync_property_text()
        self.status = f"Custom shape with {len(points)} points placed. Double-click it to edit its points."

    # ------------------------------------------------------------------ events

    def handle_event(self, event, rect):
        """Process one event; `rect` is the area of the window given to the builder."""
        lay = self._layout(rect)
        if self.save_dialog:
            self._dialog_event(event, rect, lay["unit"])
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._mouse_down(event.pos, lay)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._right_click(event.pos, lay)
        elif event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
            self._mouse_move(event, lay["canvas"])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._mouse_up(event.pos, lay)
        elif event.type == pygame.KEYDOWN:
            self._key_down(event)

    def _mouse_down(self, position, lay):
        self.mouse = position
        if self.active_property is not None:           # clicking elsewhere confirms the field
            self._apply_property(self.active_property)
            self.active_property = None
        if not lay["clear"].collidepoint(position):
            self.clear_armed_until = 0

        if lay["save"].collidepoint(position):
            self.save_name_text = self.map_name
            self.save_name_select_all = True
            self.save_dialog = True
            return
        if lay["clear"].collidepoint(position):
            now = pygame.time.get_ticks()
            if now < self.clear_armed_until:           # second click confirms
                self.__init__(self.on_saved)
                self.status = "Canvas cleared."
            elif self.shapes:
                self.clear_armed_until = now + 3000
            return
        for kind, item in lay["items"].items():
            if item.collidepoint(position):
                self._arm(kind)
                return
        shape = self._selected_shape()
        if shape is not None and lay["properties"].collidepoint(position):
            self._property_click(position, lay, shape)
            return
        if lay["canvas"].collidepoint(position):
            self._canvas_down(position, lay["canvas"])

    def _canvas_down(self, position, canvas):
        point = _clamp_point(self._to_map(position, canvas))
        if self.drawing is not None:
            self._draw_click(position, point, canvas)
            return
        if self.pending:
            self._place(self.pending, point)
            self.pending = None
            return

        shape = self._selected_shape()
        if shape is not None and not shape.locked:
            if self.editing:
                vertex = self._hit_vertex(position, canvas, shape)
                if vertex is not None:
                    self.drag = ("vertex", vertex)
                    return
                if shape.kind == "polygon":
                    edge = self._hit_midpoint(position, canvas, shape)
                    if edge is not None:               # new point between two existing ones
                        points = shape.points()
                        points.insert(edge + 1, point)
                        shape.set_points(points)
                        self.drag = ("vertex", edge + 1)
                        return
            else:
                handle = self._hit_handle(position, canvas, shape)
                if handle == "rotate":
                    self.drag = ("rotate",)
                    return
                if handle is not None:
                    initial = (shape.cx, shape.cy, shape.width, shape.height, shape.angle)
                    self.drag = ("resize", handle[0], handle[1], initial)
                    return

        index = self._hit_shape(point)
        now = pygame.time.get_ticks()
        double = index is not None and index == self.last_click[0] and now - self.last_click[1] < 400
        self.last_click = (index, now)
        if index != self.selected:
            self.editing = False
        self.selected = index
        self._sync_property_text()
        if index is None:
            self.status = "Nothing selected."
            return
        shape = self.shapes[index]
        if shape.locked:
            self.status = "This shape is locked."
        elif double and shape.kind in EDITABLE and not self.editing:
            self._toggle_editing()
        else:
            self.drag = ("move", shape.cx - point[0], shape.cy - point[1])

    def _right_click(self, position, lay):
        canvas = lay["canvas"]
        if self.drawing is not None:
            self._finish_drawing()
            return
        shape = self._selected_shape()
        if shape is None or not self.editing or shape.kind != "polygon" or shape.locked:
            return
        vertex = self._hit_vertex(position, canvas, shape)
        if vertex is None:
            return
        points = shape.points()
        if len(points) <= 3:
            self.status = "A shape needs at least 3 points."
            return
        points.pop(vertex)
        shape.set_points(points)
        self._sync_property_text()

    def _mouse_move(self, event, canvas):
        point = self._to_map(event.pos, canvas)
        if self.drawing is not None:
            if self.freehand and event.buttons[0] and self.drawing:
                point = _clamp_point(point)
                last = self.drawing[-1]
                if hypot(point[0] - last[0], point[1] - last[1]) >= FREEHAND_STEP:
                    self.drawing.append(point)
            return
        shape = self._selected_shape()
        if self.drag is not None and not event.buttons[0]:
            self.drag = None                       # the button was released outside the tab
        if self.drag is None or shape is None or shape.locked:
            return
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        action = self.drag[0]
        if action == "move":
            shape.cx = max(0.0, min(LOGICAL_SIZE[0], point[0] + self.drag[1]))
            shape.cy = max(0.0, min(LOGICAL_SIZE[1], point[1] + self.drag[2]))
        elif action == "rotate":
            angle = degrees(atan2(point[1] - shape.cy, point[0] - shape.cx)) + 90
            shape.angle = round(angle / 15) * 15 if shift else angle     # Shift snaps to 15 degrees
        elif action == "resize":
            _, sx, sy, initial = self.drag
            # corners keep the proportions unless Shift is held; side handles always stretch
            resize_shape(shape, initial, sx, sy, point, proportional=not shift)
        elif action == "vertex":
            shape.move_vertex(self.drag[1], _clamp_point(point))
        if self.active_property is None:
            self._sync_property_text()

    def _mouse_up(self, position, lay):
        if self.pending and self.pending_pressed:
            self.pending_pressed = False
            if lay["canvas"].collidepoint(position):           # dragged from the palette
                self._place(self.pending, self._to_map(position, lay["canvas"]))
                self.pending = None
            elif not lay["items"][self.pending].collidepoint(position):
                self.pending = None                            # dropped outside: cancel
        self.freehand = False
        self.drag = None

    def _key_down(self, event):
        if self.active_property is not None:
            name = self.active_property
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._apply_property(name)
                self.active_property = None
            elif event.key == pygame.K_ESCAPE:
                self.active_property = None
                self._sync_property_text()
            elif event.key == pygame.K_BACKSPACE:
                self.property_text[name] = "" if self.property_select_all else self.property_text[name][:-1]
            elif event.unicode and event.unicode in "0123456789.-":
                if self.property_select_all:
                    self.property_text[name] = ""
                self.property_text[name] += event.unicode
            else:
                return
            self.property_select_all = False
        elif self.drawing is not None:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._finish_drawing()
            elif event.key == pygame.K_BACKSPACE and self.drawing:
                self.drawing.pop()
            elif event.key == pygame.K_ESCAPE:
                self.drawing = None
                self.freehand = False
                self.status = "Drawing cancelled."
        elif event.key == pygame.K_DELETE:
            self._delete_selected()
        elif event.key == pygame.K_ESCAPE:
            if self.pending:
                self.pending = None
            elif self.editing:
                self.editing = False
            else:
                self.selected = None
                self._sync_property_text()

    def _dialog_event(self, event, rect, unit):
        _, field, save_rect, cancel_rect = self._save_dialog_rects(rect, unit)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if field.collidepoint(event.pos):
                self.save_name_select_all = True
            elif save_rect.collidepoint(event.pos):
                self._save_named_map()
            elif cancel_rect.collidepoint(event.pos):
                self.save_dialog = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._save_named_map()
            elif event.key == pygame.K_ESCAPE:
                self.save_dialog = False
            elif event.key == pygame.K_a and (event.mod & pygame.KMOD_CTRL):
                self.save_name_select_all = True
            elif event.key == pygame.K_BACKSPACE:
                self.save_name_text = "" if self.save_name_select_all else self.save_name_text[:-1]
                self.save_name_select_all = False
            elif event.unicode and event.unicode.isprintable():
                if self.save_name_select_all:
                    self.save_name_text = ""
                    self.save_name_select_all = False
                self.save_name_text += event.unicode

    def _save_named_map(self):
        if not self.shapes:
            self.status = "Nothing to save: place at least one shape."
            self.save_dialog = False
            return
        try:
            path = save_svg(self.shapes, name=self.save_name_text)
        except (OSError, ValueError) as exc:
            self.status = f"Save failed: {exc}"
            return
        self.map_name = path.stem
        self.status = f"Saved {path.name}. It is now selected in the simulation tabs."
        self.save_dialog = False
        if self.on_saved:
            self.on_saved(path)

    # ------------------------------------------------------------------ drawing

    def draw(self, surface, rect, colors, border):
        lay = self._layout(rect)
        unit, canvas = lay["unit"], lay["canvas"]
        clear_armed = pygame.time.get_ticks() < self.clear_armed_until
        draw_button(surface, lay["save"], "Save Map", False, border, colors)
        draw_button(surface, lay["clear"], "Sure?" if clear_armed else "Clear", clear_armed, border, colors)

        self._draw_palette(surface, lay, colors, border)
        if self.active_property is None:
            self._sync_property_text()
        self._draw_properties(surface, lay, colors, border)

        pygame.draw.rect(surface, colors["map_bg"], canvas)
        for i in range(1, 10):                                  # guide lines every 100 units
            x = canvas.x + canvas.w * i // 10
            y = canvas.y + canvas.h * i // 10
            pygame.draw.line(surface, colors["active"], (x, canvas.y), (x, canvas.bottom - 1))
            pygame.draw.line(surface, colors["active"], (canvas.x, y), (canvas.right - 1, y))
        surface.set_clip(canvas)
        for shape in self.shapes:
            polygon = [self._to_screen(point, canvas) for point in shape.points()]
            pygame.draw.polygon(surface, colors["obstacle"], polygon)
            pygame.draw.polygon(surface, colors["fg"], polygon, 2)
        selected = self._selected_shape()
        if selected is not None:
            self._draw_selection(surface, selected, canvas, colors)
        self._draw_pending(surface, canvas, colors)
        self._draw_custom_preview(surface, canvas, colors)
        surface.set_clip(None)
        pygame.draw.rect(surface, colors["fg"], canvas, border)

        font = fit_font(self.status, lay["status"].w, unit)
        text = font.render(self.status, True, colors["fg"])
        surface.blit(text, text.get_rect(center=lay["status"].center))
        if self.save_dialog:
            self._draw_save_dialog(surface, rect, unit, colors, border)

    @staticmethod
    def _icon_points(kind, box):
        """Outline of a palette icon inside `box`."""
        cx, cy, w, h = box.centerx, box.centery, box.w, box.h
        if kind == "rectangle":
            return [(cx - w * 0.5, cy - h * 0.32), (cx + w * 0.5, cy - h * 0.32),
                    (cx + w * 0.5, cy + h * 0.32), (cx - w * 0.5, cy + h * 0.32)]
        if kind == "triangle":
            half = min(w * 0.5, h / (2 * EQUILATERAL))
            return [(cx - half, cy + half * EQUILATERAL), (cx + half, cy + half * EQUILATERAL),
                    (cx, cy - half * EQUILATERAL)]
        if kind == "circle":
            return [(cx + w * 0.5 * cos(2 * pi * i / 32), cy + h * 0.36 * sin(2 * pi * i / 32))
                    for i in range(32)]
        unit_shape = [(-0.5, -0.1), (-0.2, -0.5), (0.15, -0.25), (0.5, -0.45),
                      (0.35, 0.15), (0.5, 0.5), (-0.05, 0.3), (-0.4, 0.5)]
        return [(cx + x * w, cy + y * h) for x, y in unit_shape]

    def _draw_palette(self, surface, lay, colors, border):
        palette, unit, pad = lay["palette"], lay["unit"], lay["pad"]
        pygame.draw.rect(surface, colors["fg"], palette, border)
        draw_centered_text(surface, pygame.Rect(palette.x, palette.y, palette.w, int(unit * 1.8)),
                           "Shapes", colors, unit)
        for kind, item in lay["items"].items():
            active = self.pending == kind or (kind == "custom" and self.drawing is not None)
            pygame.draw.rect(surface, colors["active"] if active else colors["map_bg"], item)
            pygame.draw.rect(surface, colors["fg"], item, 1)
            label_h = int(unit * 1.5)
            icon_side = max(10, min(item.w - 4 * pad, item.h - label_h - 2 * pad))
            box = pygame.Rect(0, 0, icon_side, icon_side)
            box.center = (item.centerx, item.y + (item.h - label_h) // 2)
            pygame.draw.polygon(surface, colors["obstacle"], self._icon_points(kind, box), 3)
            font = fit_font(LABELS[kind], item.w - pad, int(unit * 0.9))
            text = font.render(LABELS[kind], True, colors["fg"])
            surface.blit(text, text.get_rect(midbottom=(item.centerx, item.bottom - pad // 2)))

    def _draw_properties(self, surface, lay, colors, border):
        rect, unit, pad = lay["properties"], lay["unit"], lay["pad"]
        pygame.draw.rect(surface, colors["fg"], rect, border)
        title_h = int(unit * 1.8)
        draw_centered_text(surface, pygame.Rect(rect.x, rect.y, rect.w, title_h), "Properties", colors, unit)
        shape = self._selected_shape()
        if shape is None:
            if self.drawing is not None:
                lines = ["Custom shape:", "click = add a point", "hold + drag = freehand",
                         "Backspace = undo point", "Enter / right click = close", "Esc = cancel"]
            else:
                lines = ["No shape selected.", "", "Corner handle = resize", "Side handle = stretch",
                         "Round handle = rotate", "Shift = free corner / 15 deg",
                         "Double click = edit points", "Delete = remove shape"]
            size = int(unit * 0.85)
            for i, line in enumerate(lines):
                font = fit_font(line, rect.w - 2 * pad, size)
                surface.blit(font.render(line, True, colors["fg"]),
                             (rect.x + pad, rect.y + title_h + i * int(size * 1.5)))
            return

        rows = self._property_layout(lay, shape)
        size = min(int(unit * 0.9), rows["lock"].h - 6)

        def label(text, field):
            font = fit_font(text, field.x - rect.x - 2 * pad, size)
            rendered = font.render(text, True, colors["fg"])
            surface.blit(rendered, rendered.get_rect(midleft=(rect.x + pad, field.centery)))

        def value(text, field, highlight):
            pygame.draw.rect(surface, colors["active"] if highlight else colors["map_bg"], field)
            pygame.draw.rect(surface, colors["fg"], field, 1)
            font = fit_font(text, field.w - 8, size)
            rendered = font.render(text, True, colors["fg"])
            surface.blit(rendered, rendered.get_rect(midleft=(field.x + 4, field.centery)))

        label(LABELS[shape.kind], rows["lock"])
        value("Locked" if shape.locked else "Unlocked", rows["lock"], shape.locked)
        for name, field in rows["fields"].items():
            label(FIELD_LABELS[name], field)
            value(self.property_text.get(name, ""), field, name == self.active_property)
        if rows["edit"] is not None:
            draw_button(surface, rows["edit"], "Done" if self.editing else "Edit points",
                        self.editing, border, colors)
        draw_button(surface, rows["delete"], "Delete", False, border, colors)

    def _draw_selection(self, surface, shape, canvas, colors):
        if self.editing:
            if shape.kind == "polygon":
                for spot in self._edge_midpoints(shape, canvas):       # where a point can be added
                    pygame.draw.circle(surface, colors["bg"], spot, 5)
                    pygame.draw.circle(surface, VERTEX_COLOR, spot, 5, 2)
            for point in shape.points():
                spot = self._to_screen(point, canvas)
                pygame.draw.circle(surface, VERTEX_COLOR, spot, 8)
                pygame.draw.circle(surface, colors["fg"], spot, 8, 1)
            return
        handles, top_mid, rotate_tip = self._handles(shape, canvas)
        color = colors["active"] if shape.locked else HANDLE_COLOR
        pygame.draw.lines(surface, color, True, [spot for _, _, spot in handles[:4]], 2)
        if shape.locked:
            return
        pygame.draw.line(surface, color, top_mid, rotate_tip, 2)
        for sx, sy, spot in handles:
            half = 6 if sx and sy else 5
            box = pygame.Rect(spot[0] - half, spot[1] - half, 2 * half, 2 * half)
            pygame.draw.rect(surface, color if sx and sy else colors["bg"], box)   # side handles are hollow
            pygame.draw.rect(surface, color, box, 2)
        pygame.draw.circle(surface, color, rotate_tip, 8)

    def _draw_pending(self, surface, canvas, colors):
        """Ghost of the shape that will be placed at the mouse position."""
        if not self.pending or not canvas.collidepoint(self.mouse):
            return
        x, y = self._to_map(self.mouse, canvas)
        height = 150.0 * EQUILATERAL if self.pending == "triangle" else 100.0
        ghost = PlacedShape(self.pending, x, y, 150.0, height)
        if self.pending == "circle":
            ghost.width = ghost.height = 125.0
        pygame.draw.polygon(surface, HANDLE_COLOR, [self._to_screen(p, canvas) for p in ghost.points()], 2)

    def _draw_custom_preview(self, surface, canvas, colors):
        if self.drawing is None:
            return
        spots = [self._to_screen(point, canvas) for point in self.drawing]
        if len(spots) >= 2:
            pygame.draw.lines(surface, VERTEX_COLOR, False, spots, 3)
        if spots and canvas.collidepoint(self.mouse) and not self.freehand:
            pygame.draw.line(surface, VERTEX_COLOR, spots[-1], self.mouse, 1)       # rubber band
        if len(spots) <= 40:                         # freehand strokes are too dense for dots
            for spot in spots[1:]:
                pygame.draw.circle(surface, VERTEX_COLOR, spot, 4)
        if spots:                                    # the first point is the "close" target
            pygame.draw.circle(surface, colors["bg"], spots[0], 9)
            pygame.draw.circle(surface, VERTEX_COLOR, spots[0], 9, 3)

    def _draw_save_dialog(self, surface, rect, unit, colors, border):
        dialog, field, save_rect, cancel_rect = self._save_dialog_rects(rect, unit)
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        surface.blit(overlay, rect.topleft)
        pygame.draw.rect(surface, colors["map_bg"], dialog)
        pygame.draw.rect(surface, colors["fg"], dialog, border)
        draw_centered_text(surface, pygame.Rect(dialog.x, dialog.y + unit, dialog.w, unit * 2),
                           "Save Map", colors, int(unit * 1.3))
        pygame.draw.rect(surface, colors["active"] if self.save_name_select_all else colors["bg"], field)
        pygame.draw.rect(surface, colors["fg"], field, border)
        font = fit_font(self.save_name_text, field.w - 16, int(unit * 1.2))
        text = font.render(self.save_name_text, True, colors["fg"])
        surface.blit(text, text.get_rect(midleft=(field.x + 8, field.centery)))
        draw_button(surface, save_rect, "Save", False, border, colors)
        draw_button(surface, cancel_rect, "Cancel", False, border, colors)
