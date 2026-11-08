import math

from MapBuilder.map_builder import PlacedShape, save_svg
from svg_loader import load_map


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
    ]
    path = save_svg(shapes, tmp_path, "smoke_map")
    loaded = load_map(path)
    assert loaded.bounds == (0.0, 0.0, 1000.0, 1000.0)
    assert len(loaded.obstacles) == 3


def test_save_svg_rejects_empty_name(tmp_path):
    try:
        save_svg([], tmp_path, "...")
    except ValueError:
        pass
    else:
        raise AssertionError("empty/invalid map names must be rejected")
