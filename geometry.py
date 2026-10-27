"""Testul „ce conține acest dreptunghi?” față de obstacolele hărții, cu shapely."""
import shapely
from shapely.geometry import Polygon, box

FREE = "free"      # nu atinge niciun obstacol (sau doar îl atinge pe margine)
FULL = "full"      # complet în interiorul obstacolelor
MIXED = "mixed"    # parțial ocupat


def obstacles_geometry(map_data):
    """Reuniunea tuturor obstacolelor, pregătită pentru teste repetate rapide."""
    polygons = [shapely.make_valid(Polygon(points)) for points in map_data.obstacles]
    union = shapely.union_all(polygons)
    shapely.prepare(union)
    return union


def classify(geometry, x, y, w, h):
    cell = box(x, y, x + w, y + h)
    # o celulă care doar atinge un obstacol pe margine (fără suprafață comună) e liberă
    if not geometry.intersects(cell) or geometry.touches(cell):
        return FREE
    if geometry.contains(cell):
        return FULL
    return MIXED
