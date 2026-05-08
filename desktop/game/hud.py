"""Heads-up display."""
from __future__ import annotations
import pygame

from .constants import SCREEN_W, SCREEN_H
from . import render as R


ZONE_NAMES = ["Sandstone Outskirts", "Da Vinci's Forge", "Sky Workshop"]


class HUD:
    def __init__(self) -> None:
        self.font_xs   = pygame.font.SysFont("consolas", 12)
        self.font_sm   = pygame.font.SysFont("consolas", 14)
        self.font_md   = pygame.font.SysFont("consolas", 18, bold=True)
        self.font_big  = pygame.font.SysFont("consolas", 36, bold=True)
        self.font_huge = pygame.font.SysFont("consolas", 56, bold=True)
        # Hit-rects for the audio mute buttons (set during draw_audio_buttons).
        self.music_btn_rect: pygame.Rect | None = None
        self.sfx_btn_rect: pygame.Rect | None = None

    def _text(self, surf, font, text, pos, color=R.BONE, shadow=True):
        if shadow:
            sh = font.render(text, True, R.STONE_DARK)
            surf.blit(sh, (pos[0] + 1, pos[1] + 1))
        img = font.render(text, True, color)
        surf.blit(img, pos)

    def _heart_icon(self, surf, x, y, full: bool):
        c = R.HEART_RED if full else R.STONE_DARK
        pygame.draw.circle(surf, c, (x - 4, y - 2), 5)
        pygame.draw.circle(surf, c, (x + 4, y - 2), 5)
        pygame.draw.polygon(surf, c, [(x - 8, y - 1), (x + 8, y - 1), (x, y + 8)])
        if full:
            pygame.draw.circle(surf, R.BONE, (x - 5, y - 4), 1)

    # ------------------------------------------------------------------
    # Audio mute buttons (top-right corner)
    # ------------------------------------------------------------------
    def _draw_speaker_icon(self, surf, cx, cy, muted: bool, color):
        # Speaker cone — small trapezoid with a square back.
        pygame.draw.rect(surf, color, (cx - 7, cy - 3, 4, 6))
        pygame.draw.polygon(
            surf, color,
            [(cx - 3, cy - 5), (cx + 3, cy - 8), (cx + 3, cy + 8), (cx - 3, cy + 5)]
        )
        if muted:
            # Diagonal slash through the icon.
            pygame.draw.line(surf, R.BLOOD, (cx - 8, cy - 8), (cx + 8, cy + 8), 2)
        else:
            # Two sound waves to the right.
            pygame.draw.arc(surf, color,
                            pygame.Rect(cx + 2, cy - 6, 8, 12), -1.0, 1.0, 1)
            pygame.draw.arc(surf, color,
                            pygame.Rect(cx + 5, cy - 8, 10, 16), -1.0, 1.0, 1)

    def _draw_note_icon(self, surf, cx, cy, muted: bool, color):
        # Stem.
        pygame.draw.line(surf, color, (cx + 4, cy - 8), (cx + 4, cy + 4), 2)
        # Note head.
        pygame.draw.ellipse(surf, color, pygame.Rect(cx - 2, cy + 1, 7, 5))
        # Flag.
        pygame.draw.line(surf, color, (cx + 4, cy - 8), (cx + 9, cy - 4), 2)
        if muted:
            pygame.draw.line(surf, R.BLOOD, (cx - 6, cy - 8), (cx + 10, cy + 8), 2)

    def draw_audio_buttons(self, surf, *, music_muted: bool, sfx_muted: bool):
        """Render two clickable mute icons in the top-right corner.

        Stores hit rectangles on `self` so the input layer can test clicks.
        """
        # Music note (M)
        m_rect = pygame.Rect(SCREEN_W - 64, 4, 24, 22)
        # SFX speaker (N)
        s_rect = pygame.Rect(SCREEN_W - 32, 4, 24, 22)
        self.music_btn_rect = m_rect
        self.sfx_btn_rect = s_rect

        for rect, muted in ((m_rect, music_muted), (s_rect, sfx_muted)):
            bg = pygame.Surface(rect.size, pygame.SRCALPHA)
            bg.fill((20, 16, 12, 170) if not muted else (40, 18, 16, 200))
            surf.blit(bg, rect.topleft)
            pygame.draw.rect(surf, R.STONE_DARK, rect, 1)

        col_m = R.STONE_DARK if music_muted else R.GLYPH_GLOW
        col_s = R.STONE_DARK if sfx_muted else R.BONE
        self._draw_note_icon(surf, m_rect.centerx, m_rect.centery, music_muted, col_m)
        self._draw_speaker_icon(surf, s_rect.centerx, s_rect.centery, sfx_muted, col_s)

        # Tiny key hint below.
        hint = self.font_xs.render("M  N", True, R.SAND_LIGHT)
        surf.blit(hint, (SCREEN_W - 56, 26))

    def hit_test_audio_buttons(self, pos) -> str | None:
        """Returns 'music', 'sfx', or None for the given (x, y) click."""
        if pos is None:
            return None
        if self.music_btn_rect and self.music_btn_rect.collidepoint(pos):
            return "music"
        if self.sfx_btn_rect and self.sfx_btn_rect.collidepoint(pos):
            return "sfx"
        return None

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

        # Right: zone name (shifted left to leave room for the audio buttons).
        zname = ZONE_NAMES[min(zone_idx, len(ZONE_NAMES) - 1)]
        zt = self.font_md.render(zname, True, R.GLYPH_GLOW)
        surf.blit(zt, (SCREEN_W - zt.get_width() - 78, 4))

        # Bottom controls.
        hint = "A/D run   Space jump (x2)   Shift dash   S slide   E glyph-bomb   R restart   M music   N sfx"
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
        title = self.font_huge.render("BABEL'S GLYPH", True, R.GLYPH_GLOW)
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 90))
        sub = self.font_md.render("An Endless Run Through Ancient Tech", True, R.BONE)
        surf.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 158))

        lines = [
            "Outrun the collapsing past. Avoid hazards. Collect glyphs.",
            "",
            "A / D    run / drift",
            "Space    jump  (press again in air to double-jump)",
            "Shift    dash (also kills automatons)",
            "S        slide / crouch",
            "E        throw glyph-bomb",
            "Press against a wall while falling to wall-slide; jump for wall-jump.",
            "M / N    mute music / sfx",
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
        msg = "BURIED BY TIME"
        t = self.font_huge.render(msg, True, R.BLOOD)
        surf.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 120))

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
