"""Metoda omogenă: o grilă nx × ny peste hartă, calculată dintr-odată."""
from geometry import FREE, classify, obstacles_geometry
from model import Cell, Decomposition


def build_grid(map_data, nx: int, ny: int) -> Decomposition:
    """Celulele grilei; o celulă e liberă doar dacă nu are nimic comun cu obstacolele.

    Celulele parțial ocupate sunt considerate ocupate (descompunere aproximativă).
    Id-urile sunt în ordinea rândurilor: id = rând * nx + coloană.
    """
    geometry = obstacles_geometry(map_data)
    bx, by, bw, bh = map_data.bounds
    cw, ch = bw / nx, bh / ny

    cells = {}
    for j in range(ny):
        for i in range(nx):
            x, y = bx + i * cw, by + j * ch
            cid = j * nx + i
            free = classify(geometry, x, y, cw, ch) == FREE
            cells[cid] = Cell(cid, x, y, cw, ch, free, i, j)
    return Decomposition(bounds=map_data.bounds, cols=nx, rows=ny, cells=cells)
