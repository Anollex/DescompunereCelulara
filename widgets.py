"""Fonturi și componentele de interfață: butoane, slidere, panouri."""
import pygame

# ---------------------------------------------------------------- fonturi

_font_cache = {}


def get_font(size):
    size = max(10, size)
    if size not in _font_cache:
        _font_cache[size] = pygame.font.SysFont("monospace", size)
    return _font_cache[size]


def fit_font(text, max_w, max_h):
    """Cel mai mare font (pornind de la max_h) la care `text` încape în lățimea max_w."""
    size = max(10, max_h)
    while size > 10 and get_font(size).size(text)[0] > max_w:
        size -= 1
    return get_font(size)


def uniform_font(texts, max_w, max_h):
    """Un singur font pentru mai multe texte: cel mai mare la care încap toate."""
    return min((fit_font(text, max_w, max_h) for text in texts), key=lambda font: font.get_height())


# ---------------------------------------------------------------- slider

class Slider:
    """Ține doar starea (valoare, tragere). Dreptunghiul vine din layout la fiecare cadru."""

    def __init__(self, label, lo, hi, value):
        self.label = label
        self.lo = lo
        self.hi = hi
        self.value = value
        self.dragging = False

    @staticmethod
    def _track(rect):
        """Capetele pistei și raza butonului, calculate din dreptunghiul sliderului."""
        radius = max(6, rect.h // 4)
        x0 = rect.x + int(rect.w * 0.34) + radius     # stânga e rezervată textului
        x1 = rect.right - radius
        return x0, x1, rect.centery, radius

    def _set_from_x(self, x, rect):
        x0, x1, _, _ = self._track(rect)
        t = (x - x0) / max(1, x1 - x0)
        t = max(0.0, min(1.0, t))                     # nu ieși din capete
        self.value = self.lo + round(t * (self.hi - self.lo))

    def handle(self, ev, rect):
        x0, x1, _, radius = self._track(rect)
        hit = pygame.Rect(x0 - radius, rect.y, (x1 - x0) + 2 * radius, rect.h)
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and hit.collidepoint(ev.pos):
            self.dragging = True
            self._set_from_x(ev.pos[0], rect)         # un click sare direct acolo
        elif ev.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from_x(ev.pos[0], rect)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.dragging = False                     # oriunde ar fi mouse-ul

    def draw(self, surface, rect, border, colors):
        x0, x1, cy, radius = self._track(rect)

        text = f"{self.label}: {self.value}"
        font = fit_font(text, int(rect.w * 0.32), rect.h // 2)
        label = font.render(text, True, colors["fg"])
        surface.blit(label, label.get_rect(midleft=(rect.x, cy)))

        pygame.draw.line(surface, colors["fg"], (x0, cy), (x1, cy), max(2, border * 2))
        t = (self.value - self.lo) / (self.hi - self.lo)
        knob = (round(x0 + t * (x1 - x0)), cy)
        pygame.draw.circle(surface, colors["active"] if self.dragging else colors["bg"], knob, radius)
        pygame.draw.circle(surface, colors["fg"], knob, radius, max(1, border))


# ---------------------------------------------------------------- butoane și panouri

def draw_button(surface, rect, text, active, border, colors, font=None):
    """Buton / tab. `font` se dă când mai multe butoane trebuie să aibă aceeași mărime de text."""
    if active:
        pygame.draw.rect(surface, colors["active"], rect)   # umplut doar dacă e activ
    pygame.draw.rect(surface, colors["fg"], rect, border)   # contur mereu
    if font is None:
        font = fit_font(text, int(rect.w * 0.9), rect.h // 2)   # textul nu iese din buton
    label = font.render(text, True, colors["fg"])
    surface.blit(label, label.get_rect(center=rect.center))


def draw_theme_button(surface, rect, theme_name, border, colors):
    # Butonul arată tema în care TRECI: soare în dark, lună în light
    pygame.draw.rect(surface, colors["fg"], rect, border)
    radius = rect.h // 4
    if theme_name == "dark":
        pygame.draw.circle(surface, colors["fg"], rect.center, radius)          # soare
    else:
        pygame.draw.circle(surface, colors["fg"], rect.center, radius)          # lună:
        offset = (rect.centerx + radius // 2, rect.centery - radius // 2)       # un cerc plin
        pygame.draw.circle(surface, colors["bg"], offset, radius)               # „mușcat” de altul


def panel_content(rect, border, size):
    """Zona de conținut a unui panou, sub antet. Depinde doar de dimensiuni, nu de text,
    deci conținutul nu se mută când se schimbă mesajul din antet."""
    inset = max(4, border * 3)
    top = rect.y + 2 * inset + get_font(size).get_height()
    return pygame.Rect(rect.x + inset, top, rect.w - 2 * inset, rect.bottom - inset - top)


def draw_panel(surface, rect, title, border, colors, size, status=""):
    """Contur + antet pe o singură linie: titlul în stânga, starea în dreapta.

    Întoarce zona de conținut (aceeași ca panel_content)."""
    pygame.draw.rect(surface, colors["fg"], rect, border)
    inset = max(4, border * 3)
    title_font = get_font(size)
    line_h = title_font.get_height()
    label = title_font.render(title, True, colors["fg"])
    surface.blit(label, (rect.x + inset, rect.y + inset))
    if status:
        # starea se micșorează ca să încapă, dar rămâne centrată pe aceeași linie
        room = rect.w - 3 * inset - label.get_width() - size
        font = fit_font(status, max(10, room), size)
        text = font.render(status, True, colors["fg"])
        surface.blit(text, text.get_rect(midright=(rect.right - inset, rect.y + inset + line_h // 2)))
    content = panel_content(rect, border, size)
    y = content.y - inset // 2
    pygame.draw.line(surface, colors["active"], (rect.x + border, y), (rect.right - border - 1, y))
    return content


def draw_centered_text(surface, rect, text, colors, size):
    font = fit_font(text, int(rect.w * 0.9), size)
    label = font.render(text, True, colors["fg"])
    surface.blit(label, label.get_rect(center=rect.center))
