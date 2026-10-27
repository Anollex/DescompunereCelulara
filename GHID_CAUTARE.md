# Ghid pentru modulul de căutare a drumului

Acest ghid explică tot ce trebuie să știi ca să implementezi căutarea drumului în
proiectul „Descompunere celulară aproximativă”. Lucrezi într-un singur fișier,
`pathfinding.py`. Restul proiectului nu trebuie modificat.

## 1. Pe scurt

Primești un **graf** (celulele libere ale hărții și vecinii lor), id-ul celulei de
**start** și id-ul celulei de **finish**. Scrii un **generator** care extinde câte un nod la
fiecare pas și notează ce a explorat într-un obiect `SearchState`. Interfața îl apelează
o dată pentru fiecare apăsare de **Step** (sau automat, la **AUTO**) și colorează celulele
după ce găsește în `SearchState`.

Proiectul conține deja un **A\* simplu**, ca restul aplicației să poată fi verificat.
Îl poți înlocui complet, cu condiția să respecți contractul din secțiunea 4.

## 2. Unde te afli în proiect

```
main.py            interfața: butoane, slidere, desenare
  └─ simulation.py   leagă fazele și le avansează câte un pas
       ├─ grid.py          metoda omogenă  ─┐
       ├─ quadtree.py      metoda arborelui ─┤─► Decomposition (celule + graf)
       │                                     │
       └─ pathfinding.py   ◄── TU ───────────┘   search(...) ─► SearchState
model.py           structurile de date comune (Cell, Decomposition, SearchState)
```

O simulare trece prin fazele de mai jos. Tu intervii doar în ultima:

| Fază | Ce se întâmplă | Al cui e codul |
|---|---|---|
| `decompose` | harta se împarte în celule (grilă sau arbore) | `grid.py`, `quadtree.py` |
| `connect` | se construiește graful celulelor libere | `model.build_adjacency` |
| `search` | **căutarea drumului, un nod pe pas** | **`pathfinding.py`** |
| `done` / `error` | rezultat afișat | `simulation.py` |

Important: **căutarea nu știe dacă graful vine din grilă sau din arbore.** Ambele metode
produc același format, deci scrii algoritmul o singură dată.

## 3. Datele pe care le primești

Toate sunt definite în `model.py`. Coordonatele sunt coordonate de **hartă** (din SVG),
nu pixeli.

### `Decomposition`

```python
decomp.graph    # dict[int, list[tuple[int, float]]]
decomp.cells    # dict[int, Cell]
```

**`decomp.graph`** este o **listă de adiacență**, doar pentru celulele libere:

```python
decomp.graph[12] == [(13, 10.0), (7, 10.0), (17, 10.0)]
#                     ^^  ^^^^
#                  vecin  costul muchiei
```

- Graful este **neorientat**: dacă `b` e vecin al lui `a`, atunci și `a` e vecin al lui `b`,
  cu același cost.
- Vecinii sunt celulele cu o **latură comună** (4-vecinătate). Diagonalele nu sunt muchii.
- **Costul** unei muchii este distanța dintre centrele celor două celule. La grilă toate
  costurile sunt egale (sau două valori, dacă celulele nu sunt pătrate). La arbore celulele
  au mărimi diferite, deci costurile diferă. **Nu presupune costuri egale.**
- Celulele ocupate **nu apar** în graf.
- Id-urile sunt întregi, dar **nu neapărat consecutivi** (la arbore au „găuri”). Folosește
  dicționare sau seturi, nu liste indexate după id.

**`decomp.cells[id]`** e un `Cell`. Probabil vei avea nevoie doar de:

```python
decomp.cells[id].center    # (x, y), centrul celulei; util pentru euristică
```

### `SearchState`

Obiectul pe care îl **completezi** tu. Îl primești gol.

| Câmp | Tip | Ce pui acolo |
|---|---|---|
| `current` | `int \| None` | nodul extins la pasul curent |
| `frontier` | `set[int]` | nodurile din coadă, încă neextinse |
| `visited` | `set[int]` | nodurile deja extinse |
| `came_from` | `dict[int, int]` | părintele fiecărui nod (opțional, util pentru drum) |
| `path` | `list[int] \| None` | la final: drumul de la start la finish, inclusiv capetele |
| `finished` | `bool` | `True` după ultimul pas |

Interfața colorează celulele după aceste câmpuri:

| Cod | Culoare | Vine din |
|---|---|---|
| 2 vizitat | albastru | `visited` |
| 3 frontieră | galben | `frontier` |
| 4 drum | mov | `path` |

## 4. Contractul (obligatoriu)

```python
def search(decomp, start_id, goal_id, state):
    ...
```

1. **Este un generator.** Face `yield` **exact o dată după fiecare nod extins.** Un `yield`
   înseamnă un Step în interfață. Ce pui după `yield` nu contează (de obicei id-ul nodului).
2. **Înainte de fiecare `yield`**, `state` trebuie să reflecte situația curentă:
   `current`, `frontier`, `visited`. Un nod nu poate fi în același timp în `frontier` și
   în `visited`.
3. **La final** setează `state.path` (lista de id-uri sau `None` dacă nu există drum) și
   `state.finished = True`, apoi generatorul se termină (`return`). Poți face sau nu un
   ultim `yield` după ce ai setat drumul. Simularea verifică `state.finished` după fiecare pas.
4. **Nu modifica** `decomp`. Folosește-l doar pentru citire.
5. **Nu importa pygame** și nu afișa nimic (nici `print` la fiecare pas). Modulul trebuie să
   poată rula și fără interfață, de exemplu în teste.
6. **Precondiții garantate de simulare:** `start_id` și `goal_id` sunt celule libere și
   există în `decomp.graph`. Pot fi egale. Graful poate fi neconex, adică drumul poate să
   nu existe.

## 5. Cum te apelează simularea

Simplificat, din `simulation.py`:

```python
state = SearchState()
generator = search(decomp, start_id, goal_id, state)

# la fiecare Step (sau la fiecare tick de AUTO):
next(generator, None)       # None = nu arunca StopIteration dacă s-a terminat
if state.finished:
    # afișează rezultatul: state.path
    ...
```

Între două `next()` interfața redesenează fereastra de câteva ori. De aceea starea trebuie
să fie corectă în orice moment dintre două pași.

## 6. Implementarea existentă

`pathfinding.py` conține un A\* cu:

- o coadă de priorități (`heapq`) ordonată după `f = g + h`;
- `h` = distanța în linie dreaptă dintre centre (funcția `heuristic`);
- un contor ca element secundar în tuplu, ca să departajeze nodurile cu același `f`;
- reconstrucția drumului din `came_from` (`reconstruct_path`).

Idei de extindere, dacă vrei:

- **Dijkstra** e același algoritm cu euristica `0`. Poți adăuga un parametru, dar
  semnătura apelată de simulare trebuie să rămână validă (dă-i o valoare implicită).
- Alte euristici (Manhattan pe centre) sau un BFS (ignoră costurile) pentru comparație.
- Dacă ai nevoie de câmpuri noi în `SearchState` (de exemplu costul `g` per nod pentru
  afișare), **anunță-ne înainte**: `model.py` e folosit și de interfață.

## 7. Testare

Testele rulează fără interfață:

```bash
python test_pathfinding.py
# sau, dacă ai pytest:
pytest test_pathfinding.py
```

Ce verifică:

| Test | Situația |
|---|---|
| `test_straight_line` | drum drept pe o hartă goală |
| `test_detour_around_obstacle` | ocolirea unui obstacol din mijloc |
| `test_no_path` | perete complet: `path` trebuie să fie `None` |
| `test_start_equals_goal` | start = finish: drumul are un singur nod |
| `test_only_four_neighbours` | graful nu are diagonale |
| `test_quadtree_cells_of_different_sizes` | drum prin celule de mărimi diferite (arbore) |

În timpul rulării, testele verifică și că niciun nod nu e simultan în `frontier` și
`visited`, că drumul merge doar pe muchii existente și doar prin celule libere.

Poți adăuga teste proprii după același model: construiești o hartă mică (`MapData` cu
obstacole ca liste de puncte), o descompui cu `build_grid` sau `QuadTreeBuilder`, apelezi
`build_adjacency` și rulezi `search`.

Pentru o verificare vizuală, pornește aplicația (`python main.py`), pune start și finish
cu click pe hartă (butonul Start/Finish alege ce punct pui) și apasă Step sau AUTO.

## 8. Înainte să predai

- [ ] `python test_pathfinding.py` trece.
- [ ] Semnătura `search(decomp, start_id, goal_id, state)` e neschimbată.
- [ ] Un `yield` per nod extins; `state` corect înainte de fiecare `yield`.
- [ ] La final: `state.path` (sau `None`) și `state.finished = True`.
- [ ] Niciun `import pygame`, niciun `print` în buclă, `decomp` nemodificat.
- [ ] Merge pe toate hărțile din `maps/`, în ambele moduri (Omogen și Arbore).
