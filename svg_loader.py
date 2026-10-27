"""Citirea hărților din fișiere SVG.

Convenția: zona hărții este viewBox-ul, iar fiecare formă din fișier este un obstacol.
Totul rămâne în coordonatele SVG; transformarea spre ecran se face în map_view.py.
"""
from dataclasses import dataclass, field
from pathlib import Path

from svgelements import SVG, Close, Line, Move, Path as SvgPath, Shape

Point = tuple[float, float]


@dataclass
class MapData:
    name: str
    bounds: tuple[float, float, float, float]          # x, y, lățime, înălțime (din viewBox)
    obstacles: list[list[Point]] = field(default_factory=list)


def list_maps(folder):
    """Toate fișierele .svg din folder, sortate după nume."""
    return sorted(Path(folder).glob("*.svg"))


def _subpath_points(subpath, curve_samples):
    """Punctele unui contur: capetele segmentelor drepte, eșantioane pe cele curbe."""
    points = []
    for seg in subpath:
        if isinstance(seg, (Move, Line, Close)):
            if seg.end is not None:
                points.append((float(seg.end.x), float(seg.end.y)))
        else:                                       # Bezier pătratic/cubic, arc
            for i in range(1, curve_samples + 1):
                p = seg.point(i / curve_samples)
                points.append((float(p.x), float(p.y)))
    return points


def _clean(points, eps=1e-9):
    """Scoate punctele duplicate consecutive și închiderea care repetă primul punct."""
    out = []
    for p in points:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= eps and abs(out[0][1] - out[-1][1]) <= eps:
        out.pop()
    return out


def load_map(path, curve_samples=16):
    path = Path(path)
    svg = SVG.parse(str(path))

    if svg.viewbox is not None:
        vb = svg.viewbox
        bounds = (float(vb.x), float(vb.y), float(vb.width), float(vb.height))
    else:
        bounds = (0.0, 0.0, float(svg.width), float(svg.height))
    if bounds[2] <= 0 or bounds[3] <= 0:
        raise ValueError(f"{path.name}: hartă fără dimensiuni (lipsesc viewBox și width/height)")

    obstacles = []
    for element in svg.elements():
        if not isinstance(element, Shape):
            continue
        # abs() aplică transformarea rămasă pe formă (de ex. o rotație pe un <rect>),
        # pe care SVG.parse nu o poate „coace” direct în x/y/width/height
        for subpath in abs(SvgPath(element)).as_subpaths():
            points = _clean(_subpath_points(subpath, curve_samples))
            if len(points) >= 3:                     # un poligon are nevoie de minim 3 puncte
                obstacles.append(points)

    return MapData(name=path.stem, bounds=bounds, obstacles=obstacles)
