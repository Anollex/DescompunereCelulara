"""Constante folosite în tot proiectul."""
from pathlib import Path

MIN_SIZE = (1280, 960)   # fereastra nu poate fi micșorată sub această dimensiune

# Culorile grupate pe roluri, câte un set pentru fiecare temă
THEMES = {
    "light": {
        "bg": (255, 255, 255), "fg": (0, 0, 0), "active": (200, 200, 200),
        "map_bg": (242, 242, 242), "obstacle": (60, 60, 60),
    },
    "dark": {
        "bg": (30, 30, 36), "fg": (230, 230, 230), "active": (70, 70, 82),
        "map_bg": (44, 44, 52), "obstacle": (160, 160, 172),
    },
}

# Înălțimea rândurilor de sub pătrate, ca fracție din latura pătratului.
# Fiind legate de latură, tot blocul se scalează uniform.
BTN_FRAC = 0.12
SLIDER_FRAC = 0.25

AUTO_STEP_MS = 20        # pauza dintre doi pași la AUTO (mai mic = mai rapid)

# Hărțile se citesc din folderul maps/ de lângă acest fișier, indiferent de unde pornești programul
MAPS_DIR = Path(__file__).resolve().parent / "maps"
CURVE_SAMPLES = 16       # câte puncte se iau pe fiecare segment curb (Bezier, arc)
