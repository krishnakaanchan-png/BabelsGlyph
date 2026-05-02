"""Heads-up display."""
from __future__ import annotations
import pygame

from .constants import SCREEN_W, SCREEN_H
from . import render as R
from . import fonts


ZONE_NAMES = ["Sandstone Outskirts", "Da Vinci's Forge", "Sky Workshop"]


class HUD:
    def __init__(self) -> None:
        # Body face (IBM Plex Sans) for HUD readouts and instructions.
        self.font_xs   = fonts.body(12, weight="regular")
        self.font_sm   = fonts.body(14, weight="regular")
        self.font_md   = fonts.body(18, weight="medium")
        # Display face (Cinzel) for titles and big stats.
        self.font_big  = fonts.display(40, bold=True)
        self.font_huge = fonts.display(64, bold=True)
        # Title gets extra letter-spacing applied at render time.
        self._title_tracking = 6

    def _text(self, surf, font, text, pos, color=R.BONE, shadow=True):
        if shadow:
            sh = font.render(text, True, R.STONE_DARK)
            surf.blit(sh, (pos[0] + 1, pos[1] + 1))
        img = font.render(text, True, color)
        surf.blit(img, pos)

    def _render_tracked(self, font, text, color, tracking):
        """Render `text` with extra horizontal spacing between glyphs.

        Cinzel's Roman caps look chiselled with a few px of tracking;
        we render each character separately and stitch them together.
        """
        glyphs = [font.render(ch, True, color) for ch in text]
        if not glyphs:
            return font.render("", True, color)
        total_w = sum(g.get_width() for g in glyphs) + tracking * (len(glyphs) - 1)
        h = max(g.get_height() for g in glyphs)
        out = pygame.Surface((total_w, h), pygame.SRCALPHA)
        x = 0
        for g in glyphs:
            out.blit(g, (x, 0))
            x += g.get_width() + tracking
        return out

    def _draw_title_text(self, surf, text, y, color, tracking=None, shadow=True):
        """Render a Cinzel display string centred at (CX, y) with shadow."""
        if tracking is None:
            tracking = self._title_tracking
        img = self._render_tracked(self.font_huge, text, color, tracking)
        x = SCREEN_W // 2 - img.get_width() // 2
        if shadow:
            sh = self._render_tracked(self.font_huge, text, R.STONE_DARK, tracking)
            surf.blit(sh, (x + 2, y + 3))
        surf.blit(img, (x, y))

    def _heart_icon(self, surf, x, y, full: bool):
        c = R.HEART_RED if full else R.STONE_DARK
        pygame.draw.circle(surf, c, (x - 4, y - 2), 5)
        pygame.draw.circle(surf, c, (x + 4, y - 2), 5)
        pygame.draw.polygon(surf, c, [(x - 8, y - 1), (x + 8, y - 1), (x, y + 8)])
        if full:
            pygame.draw.circle(surf, R.BONE, (x - 5, y - 4), 1)

    def draw_playing(self, surf, *, hp, max_hp, glyphs, distance_m, zone_idx,
                     score, highscore=None):
        # Top bar.
        s = pygame.Surface((SCREEN_W, 28), pygame.SRCALPHA)
        s.fill((20, 16, 12, 180))
        surf.blit(s, (0, 0))

        # Hearts.
        for i in range(max_hp):
            self._heart_icon(surf, 18 + i * 22, 14, full=(i < hp))

        # Glyphs counter.
        gx = 12 + max_hp * 22 + 6
        pygame.draw.circle(surf, R.GLYPH_GLOW, (gx + 8, 14), 7)
        pygame.draw.circle(surf, R.STONE_DARK, (gx + 8, 14), 7, 1)
        pygame.draw.line(surf, R.STONE_DARK, (gx + 5, 14), (gx + 11, 14), 1)
        self._text(surf, self.font_md, f"x {glyphs}", (gx + 20, 4))

        # Center: distance / score.
        center = f"{int(distance_m)} m"
        t = self.font_md.render(center, True, R.BONE)
        surf.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 4))

        # Right: zone name.
        zname = ZONE_NAMES[min(zone_idx, len(ZONE_NAMES) - 1)]
        zt = self.font_md.render(zname, True, R.GLYPH_GLOW)
        surf.blit(zt, (SCREEN_W - zt.get_width() - 12, 4))

        # Bottom controls.
        hint = "A/D run   Space jump (x2)   Shift dash   S slide   E glyph-bomb   R restart"
        t = self.font_sm.render(hint, True, R.BONE)
        # Translucent footer.
        bg = pygame.Surface((t.get_width() + 16, 20), pygame.SRCALPHA)
        bg.fill((20, 16, 12, 140))
        surf.blit(bg, (SCREEN_W // 2 - bg.get_width() // 2, SCREEN_H - 22))
        surf.blit(t, (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H - 20))

        if highscore is not None:
            ht = self.font_xs.render(f"best  {int(highscore)} m", True, R.SAND_LIGHT)
            surf.blit(ht, (SCREEN_W - ht.get_width() - 12, 32))

    def draw_title(self, surf, highscore=None):
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 110))
        surf.blit(s, (0, 0))
        self._draw_title_text(surf, "BABEL’S GLYPH", 80, R.GLYPH_GLOW)
        sub = self.font_md.render("An Endless Run Through Ancient Tech", True, R.BONE)
        surf.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 168))

        lines = [
            "Outrun the collapsing past. Avoid hazards. Collect glyphs.",
            "",
            "A / D    run / drift",
            "Space    jump  (press again in air to double-jump)",
            "Shift    dash (also kills automatons)",
            "S        slide / crouch",
            "E        throw glyph-bomb",
            "Press against a wall while falling to wall-slide; jump for wall-jump.",
            "",
            "Press SPACE to begin",
        ]
        y = 200
        for ln in lines:
            t = self.font_sm.render(ln, True, R.BONE)
            surf.blit(t, (SCREEN_W // 2 - t.get_width() // 2, y))
            y += 20

        if highscore:
            ht = self.font_md.render(f"Best run: {int(highscore)} m", True, R.GLYPH_GLOW)
            surf.blit(ht, (SCREEN_W // 2 - ht.get_width() // 2, y + 10))

    def draw_gameover(self, surf, distance_m, glyphs, highscore, new_record):
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 170))
        surf.blit(s, (0, 0))
        self._draw_title_text(surf, "BURIED BY TIME", 110, R.BLOOD)

        stats = [
            f"Distance:  {int(distance_m)} m",
            f"Glyphs:    {glyphs}",
            f"Best:      {int(highscore)} m" + ("    NEW RECORD" if new_record else ""),
        ]
        y = 230
        for ln in stats:
            color = R.GLYPH_GLOW if ("NEW RECORD" in ln) else R.BONE
            t = self.font_md.render(ln, True, color)
            surf.blit(t, (SCREEN_W // 2 - t.get_width() // 2, y))
            y += 28

        hint = self.font_md.render("Press R to restart   Esc to quit", True, R.BONE)
        surf.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, y + 20))
