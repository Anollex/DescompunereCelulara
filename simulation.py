"""Leagă fazele simulării și le avansează câte un pas.

Faze:
    "decompose" -> grilă: toată odată; arbore: o împărțire pe pas
    "connect"   -> doar la arbore: se construiește graful frunzelor libere (un pas)
    "search"    -> un nod extins pe pas (pathfinding.search)
    "done"      -> drum găsit sau inexistent
    "error"     -> startul sau finishul cade într-o celulă ocupată

Interfața folosește doar: reset(params, map_data), step(), phase, message, finished,
cell_codes(), current_cells(), decomp.
"""
import math
from dataclasses import dataclass

from grid import build_grid
from model import (FINISH, FREE, FRONTIER, OCCUPIED, PATH, PENDING, START, VISITED,
                   SearchState, build_adjacency)
from pathfinding import search
from quadtree import QuadTreeBuilder


@dataclass(frozen=True)
class SimParams:
    """Tot ce poate schimba utilizatorul. Orice schimbare relevantă = simulare nouă."""
    mode: str                                   # "grid" / "tree"
    map_name: str
    start: tuple[float, float] | None           # coordonate de hartă
    finish: tuple[float, float] | None
    nx: int
    ny: int
    depth: int

    def key(self):
        """Doar câmpurile care contează pentru modul curent (sliderul celuilalt mod nu resetează)."""
        size = (self.nx, self.ny) if self.mode == "grid" else (self.depth,)
        return (self.mode, self.map_name, self.start, self.finish) + size


class Simulation:
    def __init__(self):
        self.reset(None, None)

    def reset(self, params: SimParams | None, map_data):
        self.params = params
        self.key = params.key() if params else None
        self.map = map_data
        self.phase = "decompose"
        self.decomp = None            # Decomposition, după descompunere
        self.builder = None           # QuadTreeBuilder, doar la arbore
        self.state = None             # SearchState, în faza de căutare
        self.start_id = None
        self.goal_id = None
        self.steps = 0
        self._decompose = None
        self._search = None
        self.message = "Pune start si finish, apoi Step" if not self.ready else "Apasa Step"
        if params and map_data is not None and params.mode == "tree":
            # arborele se vede de la început (doar rădăcina); împărțirile vin cu Step
            self.builder = QuadTreeBuilder(map_data, params.depth)
            self._decompose = self.builder.steps()

    # ------------------------------------------------------------ stare

    @property
    def ready(self) -> bool:
        return (self.params is not None and self.map is not None
                and self.params.start is not None and self.params.finish is not None)

    @property
    def finished(self) -> bool:
        return self.phase in ("done", "error")

    # ------------------------------------------------------------ pas

    def step(self) -> bool:
        """Avansează un pas. Întoarce False dacă nu s-a putut face nimic."""
        if self.finished or self.map is None:
            return False
        if not self.ready:
            self.message = "Pune start si finish"
            return False
        self.steps += 1

        if self.phase == "decompose":
            if self.params.mode == "grid":
                self.decomp = build_grid(self.map, self.params.nx, self.params.ny)
                build_adjacency(self.decomp)          # la grilă, conectarea e în același pas
                self._begin_search()
            else:
                next(self._decompose, None)
                self.message = f"Impartiri: {self.builder.splits}"
                if self.builder.done:
                    self.decomp = self.builder.to_decomposition()
                    self.phase = "connect"
                    self.message = f"Arbore complet ({self.builder.splits} impartiri). Step = graf"
        elif self.phase == "connect":
            build_adjacency(self.decomp)
            self._begin_search()
        elif self.phase == "search":
            next(self._search, None)
            self.message = f"Cautare: {len(self.state.visited)} noduri extinse"
            if self.state.finished:
                self._end_search()
        return True

    def _begin_search(self):
        edges = sum(len(v) for v in self.decomp.graph.values()) // 2
        start = self.decomp.cell_at(self.params.start)
        goal = self.decomp.cell_at(self.params.finish)
        if start is None or not start.free:
            self.phase, self.message = "error", "Startul e intr-o celula ocupata"
            return
        if goal is None or not goal.free:
            self.phase, self.message = "error", "Finishul e intr-o celula ocupata"
            return
        self.start_id, self.goal_id = start.id, goal.id
        self.state = SearchState()
        self._search = search(self.decomp, start.id, goal.id, self.state)
        self.phase = "search"
        self.message = f"Graf: {len(self.decomp.graph)} noduri, {edges} muchii. Step = cautare"

    def _end_search(self):
        self.phase = "done"
        path = self.state.path
        if path is None:
            self.message = "Nu exista drum"
            return
        cost = 0.0
        for a, b in zip(path, path[1:]):
            cost += math.dist(self.decomp.cells[a].center, self.decomp.cells[b].center)
        self.message = f"Drum gasit: {len(path)} celule, lungime {cost:.1f}"

    # ------------------------------------------------------------ pentru afișare

    def current_cells(self):
        """Celulele de desenat acum: frunzele arborelui în construcție sau descompunerea finală."""
        if self.decomp is not None:
            return self.decomp.cells
        if self.builder is not None:
            return self.builder.cells
        return {}

    def cell_codes(self) -> dict[int, int]:
        """Codul de afișare al fiecărei celule (vezi constantele din model.py)."""
        codes = {}
        building = self.phase == "decompose" and self.builder is not None
        for cid, cell in self.current_cells().items():
            if building and self.builder.is_pending(cid):
                codes[cid] = PENDING
            else:
                codes[cid] = FREE if cell.free else OCCUPIED
        if self.state is not None:
            for cid in self.state.visited:
                codes[cid] = VISITED
            for cid in self.state.frontier:
                codes[cid] = FRONTIER
            for cid in self.state.path or []:
                codes[cid] = PATH
        if self.start_id is not None:
            codes[self.start_id] = START
        if self.goal_id is not None:
            codes[self.goal_id] = FINISH
        return codes
