"""Căutarea drumului pe graful celulelor libere.

>>> Ghidul complet pentru acest modul: GHID_CAUTARE.md <<<

CONTRACTUL (trebuie respectat de orice implementare):

    search(decomp, start_id, goal_id, state)

    - decomp   : model.Decomposition. Se citește doar decomp.graph (listă de adiacență
                 id -> [(vecin, cost), ...]) și, la nevoie, decomp.cells[id].center.
                 NU se modifică.
    - start_id : id-ul celulei de start (sigur liberă și prezentă în decomp.graph)
    - goal_id  : id-ul celulei de finish (sigur liberă și prezentă în decomp.graph)
    - state    : model.SearchState gol, primit de la simulare. Se modifică pe loc.

    Funcția este un GENERATOR:
    - face `yield` exact o dată după fiecare nod extins (un Step în interfață);
    - înainte de fiecare yield actualizează state.current, state.frontier, state.visited
      (și state.came_from, dacă îl folosește);
    - la final setează state.path (lista de id-uri de la start la goal inclusiv, sau None
      dacă nu există drum) și state.finished = True, apoi se oprește.

    Modulul nu importă pygame și nu afișează nimic. Interfața citește `state` la fiecare
    cadru și colorează singură celulele.

Implementarea de mai jos este un A* SIMPLU, doar ca să se poată verifica restul
proiectului. Poate fi înlocuită complet, cu condiția să păstreze semnătura și regulile.
"""
import heapq
import itertools
import math

from model import Decomposition, SearchState


def heuristic(decomp: Decomposition, a: int, b: int) -> float:
    """Distanța în linie dreaptă între centre. Cu euristica 0, A* devine Dijkstra."""
    return math.dist(decomp.cells[a].center, decomp.cells[b].center)


def reconstruct_path(came_from: dict[int, int], node: int) -> list[int]:
    path = [node]
    while node in came_from:
        node = came_from[node]
        path.append(node)
    path.reverse()
    return path


def search(decomp: Decomposition, start_id: int, goal_id: int, state: SearchState):
    order = itertools.count()                    # departajează nodurile cu același f
    g = {start_id: 0.0}                          # costul cel mai bun cunoscut de la start
    open_heap = [(heuristic(decomp, start_id, goal_id), next(order), start_id)]
    state.frontier.add(start_id)

    while open_heap:
        _, _, node = heapq.heappop(open_heap)
        if node in state.visited:                # intrare veche, nodul a fost deja extins
            continue
        state.frontier.discard(node)
        state.visited.add(node)
        state.current = node

        if node == goal_id:
            state.path = reconstruct_path(state.came_from, node)
            state.finished = True
            yield node
            return

        for neighbour, cost in decomp.graph.get(node, []):
            if neighbour in state.visited:
                continue
            new_g = g[node] + cost
            if new_g < g.get(neighbour, math.inf):
                g[neighbour] = new_g
                state.came_from[neighbour] = node
                f = new_g + heuristic(decomp, neighbour, goal_id)
                heapq.heappush(open_heap, (f, next(order), neighbour))
                state.frontier.add(neighbour)
        yield node

    state.path = None                            # coada s-a golit: nu există drum
    state.finished = True
