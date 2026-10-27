"""Structurile de date comune: contractul dintre descompunere, căutare și afișare.

Nimic de aici nu depinde de pygame. Toate coordonatele sunt coordonate de HARTĂ (SVG).

Fluxul datelor:
    grid.py / quadtree.py  ->  Decomposition (celule)
    build_adjacency()       ->  Decomposition.graph (graful celulelor libere)
    pathfinding.search()    ->  SearchState (ce s-a explorat + drumul)
"""
import math
from dataclasses import dataclass, field

Point = tuple[float, float]

# Codurile de afișare (aceleași pe hartă și în matrice)
OCCUPIED = 0   # celulă ocupată (parțial sau total)
FREE = 1       # celulă liberă
VISITED = 2    # extinsă de căutare
FRONTIER = 3   # în coada căutării, încă neextinsă
PATH = 4       # pe drumul găsit
START = 5
FINISH = 6
PENDING = 7    # doar la arbore: celulă mixtă care urmează să fie împărțită


@dataclass
class Cell:
    """O celulă dreptunghiulară a descompunerii.

    (x, y, w, h) sunt în coordonate de hartă. (i, j, ni, nj) poziționează celula pe o
    rețea întreagă de bază: coloana i, rândul j, lățime ni coloane, înălțime nj rânduri.
    La grilă fiecare celulă are ni = nj = 1. La arbore rețeaua are 2^adâncime coloane,
    iar o frunză mare acoperă mai multe coloane/rânduri. Rețeaua face găsirea vecinilor
    simplă și exactă (fără comparații cu virgulă mobilă).
    """
    id: int
    x: float
    y: float
    w: float
    h: float
    free: bool
    i: int
    j: int
    ni: int = 1
    nj: int = 1
    depth: int = 0

    @property
    def center(self) -> Point:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def contains(self, p: Point) -> bool:
        return self.x <= p[0] <= self.x + self.w and self.y <= p[1] <= self.y + self.h


@dataclass
class Decomposition:
    """Rezultatul descompunerii, identic ca formă pentru grilă și pentru arbore.

    graph este o listă de adiacență, doar pentru celulele LIBERE:
        graph[id] = [(id_vecin, cost), ...]
    Costul este distanța dintre centrele celor două celule. Vecinii sunt cei care au
    o latură comună (4-vecinătate); colțurile nu contează.
    Cât timp graful nu a fost construit, graph este un dicționar gol.
    """
    bounds: tuple[float, float, float, float]   # x, y, lățime, înălțime ale hărții
    cols: int                                   # coloanele rețelei de bază
    rows: int                                   # rândurile rețelei de bază
    cells: dict[int, Cell]
    graph: dict[int, list[tuple[int, float]]] = field(default_factory=dict)

    def cell_at(self, p: Point) -> Cell | None:
        """Celula care conține punctul p (sau None dacă e în afara hărții)."""
        for cell in self.cells.values():
            if cell.contains(p):
                return cell
        return None


@dataclass
class SearchState:
    """Starea căutării, modificată pas cu pas de pathfinding.search().

    Interfața o citește la fiecare cadru ca să coloreze celulele.
    """
    current: int | None = None                         # nodul extins la ultimul pas
    frontier: set[int] = field(default_factory=set)    # noduri în coadă, neextinse
    visited: set[int] = field(default_factory=set)     # noduri deja extinse
    came_from: dict[int, int] = field(default_factory=dict)   # părintele fiecărui nod
    path: list[int] | None = None                      # drumul start -> finish, la final
    finished: bool = False                             # True după ultimul pas


def build_adjacency(decomp: Decomposition) -> None:
    """Completează decomp.graph cu muchiile dintre celulele libere care au o latură comună."""
    # owner[rând][coloană] = id-ul celulei libere care acoperă acel pătrățel al rețelei
    owner = [[None] * decomp.cols for _ in range(decomp.rows)]
    free_cells = [c for c in decomp.cells.values() if c.free]
    for c in free_cells:
        for jj in range(c.j, c.j + c.nj):
            row = owner[jj]
            for ii in range(c.i, c.i + c.ni):
                row[ii] = c.id

    graph = {c.id: [] for c in free_cells}
    for c in free_cells:
        neighbours = set()
        right = c.i + c.ni                       # coloana imediat la dreapta celulei
        if right < decomp.cols:
            for jj in range(c.j, c.j + c.nj):
                if owner[jj][right] is not None:
                    neighbours.add(owner[jj][right])
        below = c.j + c.nj                       # rândul imediat sub celulă
        if below < decomp.rows:
            for ii in range(c.i, c.i + c.ni):
                if owner[below][ii] is not None:
                    neighbours.add(owner[below][ii])
        # verificăm doar dreapta și jos: stânga și sus le adaugă vecinul, prin simetrie
        for n in sorted(neighbours):
            cost = math.dist(c.center, decomp.cells[n].center)
            graph[c.id].append((n, cost))
            graph[n].append((c.id, cost))
    decomp.graph = graph
