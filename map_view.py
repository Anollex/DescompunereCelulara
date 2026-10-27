"""Transformarea hartă <-> ecran și desenarea hărții într-un panou."""
import pygame


class MapView:
    """Încadrează dreptunghiul hărții în `rect` fără deformare (scalare uniformă + centrare)."""

    def __init__(self, bounds, rect):
        bx, by, bw, bh = bounds
        self.scale = min(rect.w / bw, rect.h / bh)
        # unde ajunge colțul (bx, by) al hărții pe ecran
        self.ox = rect.x + (rect.w - bw * self.scale) / 2 - bx * self.scale
        self.oy = rect.y + (rect.h - bh * self.scale) / 2 - by * self.scale
        self.bounds = bounds

    def to_screen(self, x, y):
        return (self.ox + x * self.scale, self.oy + y * self.scale)

    def to_map(self, sx, sy):
        """Inversa lui to_screen: transformă un click în coordonate de hartă."""
        return ((sx - self.ox) / self.scale, (sy - self.oy) / self.scale)

    def rect_to_screen(self, x, y, w, h):
        """Dreptunghi de hartă -> pygame.Rect. Rotunjește colțurile, nu lățimea,
        ca celulele vecine să se lipească fără goluri de un pixel."""
        x0, y0 = self.to_screen(x, y)
        x1, y1 = self.to_screen(x + w, y + h)
        x0, y0, x1, y1 = round(x0), round(y0), round(x1), round(y1)
        return pygame.Rect(x0, y0, x1 - x0, y1 - y0)

    def screen_rect(self):
        """Dreptunghiul ocupat de hartă pe ecran."""
        return self.rect_to_screen(*self.bounds)


def draw_map(surface, map_data, view, border, colors):
    """Fundalul hărții și obstacolele."""
    area = view.screen_rect()
    pygame.draw.rect(surface, colors["map_bg"], area)
    for polygon in map_data.obstacles:
        pygame.draw.polygon(surface, colors["obstacle"], [view.to_screen(x, y) for x, y in polygon])
    pygame.draw.rect(surface, colors["fg"], area, border)
