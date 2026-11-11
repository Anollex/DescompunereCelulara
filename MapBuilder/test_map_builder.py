"""Tests for the map builder's shape model (no window needed).

Run from the project root:   python -m pytest MapBuilder/test_map_builder.py
"""
import math

from MapBuilder.map_builder import (EQUILATERAL, PlacedShape, polygon_area, resize_shape,
                                    save_svg, simplify_points)
from svg_loader import load_map


def side_lengths(points):
    return [math.dist(a, b) for a, b in zip(points, points[1:] + points[:1])]


def test_transformed_shape_has_expected_center():
    shape = PlacedShape("rectangle", 400, 300, 120, 80, 90)
    points = shape.points()
    assert math.isclose(sum(x for x, _ in points) / len(points), 400)
    assert math.isclose(sum(y for _, y in points) / len(points), 300)
    left, top, right, bottom = shape.bounds()
    assert math.isclose(right - left, 80, abs_tol=1e-6)
    assert math.isclose(bottom - top, 120, abs_tol=1e-6)


def test_save_svg_round_trips_as_obstacles(tmp_path):
    shapes = [
        PlacedShape("rectangle", 200, 200),
        PlacedShape("triangle", 500, 300, 120, 120, 25),
        PlacedShape("circle", 750, 450, 90, 90),
        PlacedShape.from_points([(100, 700), (300, 650), (350, 900), (200, 800), (80, 880)]),
    ]
    path = save_svg(shapes, tmp_path, "smoke_map")
    loaded = load_map(path)
    assert loaded.bounds == (0.0, 0.0, 1000.0, 1000.0)
    assert len(loaded.obstacles) == 4


def test_save_svg_rejects_empty_name(tmp_path):
    try:
        save_svg([], tmp_path, "...")
    except ValueError:
        pass
    else:
        raise AssertionError("empty/invalid map names must be rejected")


def test_circle_stretches_into_an_oval():
    shape = PlacedShape("circle", 500, 500, 100, 100)
    initial = (shape.cx, shape.cy, shape.width, shape.height, shape.angle)
    resize_shape(shape, initial, 1, 0, (700, 500))          # right side handle dragged to x = 700
    left, top, right, bottom = shape.bounds()
    assert math.isclose(left, 450, abs_tol=1e-6)            # the opposite side did not move
    assert math.isclose(right, 700, abs_tol=1e-6)
    assert math.isclose(bottom - top, 100, abs_tol=0.5)     # the other axis is unchanged


def test_corner_resize_follows_the_pointer_and_keeps_the_opposite_corner():
    shape = PlacedShape("rectangle", 500, 500, 200, 100)
    initial = (500, 500, 200, 100, 0)
    resize_shape(shape, initial, 1, 1, (700, 650))          # free resize (Shift held)
    assert shape.bounds() == (400.0, 450.0, 700.0, 650.0)
    resize_shape(shape, initial, 1, 1, (700, 650), proportional=True)
    assert math.isclose(shape.width / shape.height, 2.0)
    assert shape.bounds()[:2] == (400.0, 450.0)


def test_resize_works_on_a_rotated_shape():
    shape = PlacedShape("rectangle", 500, 500, 200, 100, 90)
    anchor = shape.to_world(-100, 0)                        # middle of the left side
    resize_shape(shape, (500, 500, 200, 100, 90), 1, 0, shape.to_world(250, 0))
    assert math.isclose(shape.width, 350)
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(shape.to_world(-175, 0), anchor))


def test_resize_never_collapses_a_shape():
    shape = PlacedShape("rectangle", 500, 500, 200, 100)
    resize_shape(shape, (500, 500, 200, 100, 0), 1, 0, (0, 500))   # dragged past the other side
    assert shape.width >= 20


def test_new_triangle_is_equilateral_and_vertices_can_move():
    shape = PlacedShape("triangle", 500, 500, 150, 150 * EQUILATERAL)
    assert all(math.isclose(side, 150, abs_tol=1e-6) for side in side_lengths(shape.points()))

    before = shape.points()
    shape.move_vertex(2, (640, 300))                        # move the top vertex
    after = shape.points()
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(after[2], (640, 300)))
    for index in (0, 1):                                    # the other two stay where they were
        assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(after[index], before[index]))


def test_moving_a_vertex_of_a_rotated_triangle_keeps_the_others():
    shape = PlacedShape("triangle", 400, 600, 150, 150 * EQUILATERAL, 37)
    before = shape.points()
    shape.move_vertex(0, (250, 720))
    after = shape.points()
    for index in (1, 2):
        assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(after[index], before[index]))
    assert math.isclose(shape.angle, 37)


def test_custom_polygon_keeps_its_points():
    points = [(100, 100), (400, 150), (350, 400), (220, 250), (120, 380)]
    shape = PlacedShape.from_points(points)
    for got, expected in zip(shape.points(), points):
        assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(got, expected))
    assert shape.bounds() == (100.0, 100.0, 400.0, 400.0)
    assert shape.contains(300, 200) and not shape.contains(230, 330)   # concave notch is outside


def test_freehand_stroke_is_simplified():
    circle = [(500 + 200 * math.cos(i / 100 * math.tau), 500 + 200 * math.sin(i / 100 * math.tau))
              for i in range(100)]
    simplified = simplify_points(circle)
    assert 8 <= len(simplified) < 60
    assert polygon_area(simplified) > 0.95 * polygon_area(circle)
