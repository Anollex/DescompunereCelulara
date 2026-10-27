"""Metoda arborelui (quadtree): rădăcina = toată harta; celulele mixte se împart în 4.

Construcția e un generator: fiecare pas împarte o singură celulă, ca să poată fi
urmărită cu Step / AUTO. Ordinea este pe niveluri (întâi toate celulele de pe nivelul 1,
apoi nivelul 2 etc.).

    builder = QuadTreeBuilder(map_data, max_depth=4)
    for split_id in builder.steps():   # un pas = o împărțire
        ...                            # builder.cells conține frunzele curente
    decomp = builder.to_decomposition()
"""
from collections import deque

from geometry import FREE, MIXED, classify, obstacles_geometry
from model import Cell, Decomposition


class QuadTreeBuilder:
    def __init__(self, map_data, max_depth: int):
        self.geometry = obstacles_geometry(map_data)
        self.bounds = map_data.bounds
        self.max_depth = max_depth
        self.size = 2 ** max_depth            # rețeaua de bază are size × size pătrățele
        self.cells: dict[int, Cell] = {}      # frunzele curente
        self.status: dict[int, str] = {}      # FREE / FULL / MIXED pentru fiecare frunză
        self.splits = 0
        self._next_id = 0
        self._queue = deque()                 # frunze mixte care încă se pot împărți

        bx, by, bw, bh = self.bounds
        self._add(bx, by, bw, bh, 0, 0, self.size, 0)

    @property
    def done(self) -> bool:
        return not self._queue

    def is_pending(self, cid: int) -> bool:
        """Celulă mixtă care va mai fi împărțită (încă nu se știe dacă e liberă sau nu)."""
        return self.status[cid] == MIXED and self.cells[cid].depth < self.max_depth

    def _add(self, x, y, w, h, i, j, n, depth):
        status = classify(self.geometry, x, y, w, h)
        cid = self._next_id
        self._next_id += 1
        # o celulă mixtă ajunsă la adâncimea maximă rămâne ocupată
        self.cells[cid] = Cell(cid, x, y, w, h, status == FREE, i, j, n, n, depth)
        self.status[cid] = status
        if status == MIXED and depth < self.max_depth:
            self._queue.append(cid)

    def steps(self):
        """Generator: la fiecare pas împarte o celulă mixtă în 4 și face yield cu id-ul ei."""
        while self._queue:
            cid = self._queue.popleft()
            cell = self.cells.pop(cid)
            self.status.pop(cid)
            hw, hh, half = cell.w / 2, cell.h / 2, cell.ni // 2
            for dy in (0, 1):
                for dx in (0, 1):
                    self._add(cell.x + dx * hw, cell.y + dy * hh, hw, hh,
                              cell.i + dx * half, cell.j + dy * half, half, cell.depth + 1)
            self.splits += 1
            yield cid

    def to_decomposition(self) -> Decomposition:
        """Frunzele finale, în formatul comun. Graful se construiește separat (faza „connect”)."""
        return Decomposition(bounds=self.bounds, cols=self.size, rows=self.size,
                             cells=dict(self.cells))
