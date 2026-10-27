"""Teste pentru pathfinding.search, fără interfață și fără pygame.

Rulare:   python test_pathfinding.py        (sau: pytest test_pathfinding.py)

Testele folosesc o hartă de 30 × 30 împărțită într-o grilă 3 × 3 (celule de 10 × 10).
Id-urile celulelor sunt în ordinea rândurilor:

    0 | 1 | 2
    ---------
    3 | 4 | 5
    ---------
    6 | 7 | 8
"""
from grid import build_grid
from model import SearchState, build_adjacency
from pathfinding import search
from svg_loader import MapData


def make_decomposition(obstacles):
    """Grilă 3×3 peste o hartă 30×30 cu obstacolele date (liste de puncte)."""
    decomp = build_grid(MapData("test", (0.0, 0.0, 30.0, 30.0), obstacles), 3, 3)
    build_adjacency(decomp)
    return decomp


def square(x, y, side=10):
    return [(x, y), (x + side, y), (x + side, y + side), (x, y + side)]


def run(decomp, start_id, goal_id):
    """Rulează căutarea până la capăt, ca simularea; întoarce (state, câți pași)."""
    state = SearchState()
    steps = 0
    for _ in search(decomp, start_id, goal_id, state):
        steps += 1
        assert not (state.frontier & state.visited), "un nod nu poate fi și în coadă și extins"
    return state, steps


def check_path(decomp, path, start_id, goal_id):
    """Drumul pornește din start, ajunge la goal și merge doar pe muchii existente."""
    assert path[0] == start_id and path[-1] == goal_id
    for a, b in zip(path, path[1:]):
        assert b in [n for n, _ in decomp.graph[a]], f"{a} -> {b} nu e muchie în graf"
        assert decomp.cells[b].free, f"celula {b} de pe drum e ocupată"


def test_straight_line():
    decomp = make_decomposition([])
    state, steps = run(decomp, 0, 2)
    assert state.finished and steps >= 1
    assert state.path == [0, 1, 2]


def test_detour_around_obstacle():
    decomp = make_decomposition([square(10, 10)])     # celula 4 (mijloc) ocupată
    assert not decomp.cells[4].free
    state, _ = run(decomp, 3, 5)
    check_path(decomp, state.path, 3, 5)
    assert 4 not in state.path
    assert len(state.path) == 5                       # 3 -> 0 -> 1 -> 2 -> 5 (sau prin jos)


def test_no_path():
    decomp = make_decomposition([[(10, 0), (20, 0), (20, 30), (10, 30)]])   # perete pe mijloc
    state, _ = run(decomp, 0, 2)
    assert state.finished and state.path is None


def test_start_equals_goal():
    decomp = make_decomposition([])
    state, _ = run(decomp, 4, 4)
    assert state.path == [4]


def test_only_four_neighbours():
    decomp = make_decomposition([])
    neighbours = sorted(n for n, _ in decomp.graph[4])
    assert neighbours == [1, 3, 5, 7]                 # fără diagonale


def test_quadtree_cells_of_different_sizes():
    """La arbore celulele au mărimi diferite; căutarea trebuie să meargă la fel."""
    from quadtree import QuadTreeBuilder
    data = MapData("test", (0.0, 0.0, 32.0, 32.0), [[(10, 0), (14, 0), (14, 24), (10, 24)]])
    builder = QuadTreeBuilder(data, max_depth=4)
    for _ in builder.steps():
        pass
    decomp = builder.to_decomposition()
    build_adjacency(decomp)
    start = decomp.cell_at((2, 2)).id
    goal = decomp.cell_at((30, 2)).id
    state, _ = run(decomp, start, goal)
    check_path(decomp, state.path, start, goal)
    sizes = {decomp.cells[c].w for c in state.path}
    assert len(sizes) > 1, "drumul ar trebui să treacă prin celule de mărimi diferite"


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"OK   {test.__name__}")
    print(f"\nToate cele {len(tests)} teste au trecut.")
