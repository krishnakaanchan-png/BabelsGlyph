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

    def draw_title(self, surf, highscore=None, *, scores=None,
                   player_name: str | None = None,
                   board_status: str | None = None,
                   gamepad_connected: bool = False):
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 110))
        surf.blit(s, (0, 0))
        title = self.font_huge.render("BABEL'S GLYPH", True, R.GLYPH_GLOW)
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 60))
        sub = self.font_md.render("An Endless Run Through Ancient Tech", True, R.BONE)
        surf.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 120))

        if player_name:
            who = self.font_sm.render(f"Welcome, {player_name}    (P to change name)",
                                      True, R.SAND_LIGHT)
            surf.blit(who, (SCREEN_W // 2 - who.get_width() // 2, 144))

        # Left column: controls / instructions.
        # Gamepad hints are always shown so players know controller
        # support exists; the 'detected' tag flips to live when a pad is
        # actually plugged in. We render keyboard and controller as two
        # side-by-side mini-columns so neither runs into the leaderboard
        # panel on the right.
        pad_status = "(detected)" if gamepad_connected else "(plug in to use)"
        kb_lines = [
            ("Keyboard",                  R.GLYPH_GLOW),
            ("A / D       run / drift",   R.BONE),
            ("Space       jump (x2)",     R.BONE),
            ("Shift       dash",          R.BONE),
            ("S           slide",         R.BONE),
            ("E           glyph-bomb",    R.BONE),
            ("M / N       mute mus/sfx",  R.BONE),
            ("P           change name",   R.BONE),
        ]
        pad_lines = [
            (f"Xbox Pad {pad_status}",    R.GLYPH_GLOW),
            ("Stick / Pad    move",       R.BONE),
            ("A              jump",       R.BONE),
            ("LB/RB or LT/RT dash",       R.BONE),
            ("Stick down     slide",      R.BONE),
            ("X              glyph-bomb", R.BONE),
            ("Y / Back       mute m/sfx", R.BONE),
            ("Start          begin",      R.BONE),
        ]

        intro = self.font_sm.render(
            "Outrun the collapsing past.  Avoid hazards.  Collect glyphs.",
            True, R.BONE,
        )
        surf.blit(intro, (60, 170))

        kb_x, pad_x, list_y = 60, 300, 200
        for i, (text, col) in enumerate(kb_lines):
            t = self.font_sm.render(text, True, col)
            surf.blit(t, (kb_x, list_y + i * 20))
        for i, (text, col) in enumerate(pad_lines):
            t = self.font_sm.render(text, True, col)
            surf.blit(t, (pad_x, list_y + i * 20))

        cta = self.font_md.render("Press SPACE or A to begin", True, R.GLYPH_GLOW)
        surf.blit(cta, (60, list_y + len(kb_lines) * 20 + 14))

        # Right column: leaderboard panel.
        self.draw_leaderboard(
            surf, scores or [], x=SCREEN_W - 360, y=170, width=320,
            highlight_name=player_name, status=board_status,
        )

        if highscore:
            ht = self.font_md.render(f"Best run: {int(highscore)} m", True, R.GLYPH_GLOW)
            surf.blit(ht, (SCREEN_W // 2 - ht.get_width() // 2, SCREEN_H - 60))

    def draw_gameover(self, surf, distance_m, glyphs, highscore, new_record,
                      *, scores=None, player_name: str | None = None,
                      board_status: str | None = None,
                      gamepad_connected: bool = False):
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
        y = 200
        for ln in stats:
            color = R.GLYPH_GLOW if ("NEW RECORD" in ln) else R.BONE
            t = self.font_md.render(ln, True, color)
            surf.blit(t, (SCREEN_W // 2 - t.get_width() // 2, y))
            y += 28

        # Leaderboard centered below stats.
        self.draw_leaderboard(
            surf, scores or [], x=SCREEN_W // 2 - 200, y=y + 8, width=400,
            highlight_name=player_name, status=board_status, max_rows=8,
        )

        hint = self.font_md.render(
            "Press R or A to restart   Esc to quit",
            True, R.BONE,
        )
        surf.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H - 36))

    # ------------------------------------------------------------------
    # Leaderboard panel
    # ------------------------------------------------------------------
    def draw_leaderboard(self, surf, scores, *, x: int, y: int, width: int,
                         highlight_name: str | None = None,
                         status: str | None = None,
                         max_rows: int = 10):
        """Render a parchment-style top-N panel."""
        title_h = 22
        row_h = 18
        rows = min(max_rows, max(1, len(scores))) if scores else 1
        body_h = title_h + rows * row_h + 10
        rect = pygame.Rect(x, y, width, body_h)

        # Translucent backing.
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill((28, 22, 16, 190))
        surf.blit(bg, rect.topleft)
        pygame.draw.rect(surf, R.GLYPH_GLOW, rect, 1)

        # Header.
        head = self.font_md.render("Top Runs (Global)", True, R.GLYPH_GLOW)
        surf.blit(head, (rect.x + 10, rect.y + 4))
        if status:
            stt = self.font_xs.render(status, True, R.SAND_LIGHT)
            surf.blit(stt, (rect.right - stt.get_width() - 8, rect.y + 8))

        if not scores:
            empty = self.font_sm.render("No scores yet — be the first!", True, R.BONE)
            surf.blit(empty, (rect.x + 10, rect.y + title_h + 4))
            return

        # Column layout: rank | name | distance | glyphs
        rank_x  = rect.x + 10
        name_x  = rect.x + 38
        dist_x  = rect.right - 120
        glyph_x = rect.right - 50

        for i, s in enumerate(scores[:max_rows]):
            row_y = rect.y + title_h + i * row_h
            name = str(s.get("name", "?"))[:14]
            dist = int(s.get("distance_m", 0))
            glyphs = int(s.get("glyphs", 0))
            is_me = (highlight_name and name == highlight_name)
            color = R.GLYPH_GLOW if is_me else R.BONE
            self._text(surf, self.font_sm, f"{i+1:>2}.",        (rank_x, row_y), color, shadow=False)
            self._text(surf, self.font_sm, name,                (name_x, row_y), color, shadow=False)
            d_text = f"{dist} m"
            d_img = self.font_sm.render(d_text, True, color)
            surf.blit(d_img, (dist_x + (60 - d_img.get_width()), row_y))
            g_img = self.font_sm.render(f"{glyphs}*", True, color)
            surf.blit(g_img, (glyph_x + (40 - g_img.get_width()), row_y))

    # ------------------------------------------------------------------
    # Name-entry overlay
    # ------------------------------------------------------------------
    def draw_name_entry(self, surf, *, current_text: str, blink_on: bool,
                        max_len: int = 12):
        """Full-screen prompt asking the player for their name."""
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 200))
        surf.blit(s, (0, 0))

        title = self.font_huge.render("BABEL'S GLYPH", True, R.GLYPH_GLOW)
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 100))

        sub = self.font_md.render(
            "Carve your name into the leaderboard:", True, R.BONE
        )
        surf.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 200))

        # Input box.
        box_w, box_h = 360, 56
        box = pygame.Rect(SCREEN_W // 2 - box_w // 2, 250, box_w, box_h)
        bg = pygame.Surface(box.size, pygame.SRCALPHA)
        bg.fill((28, 22, 16, 220))
        surf.blit(bg, box.topleft)
        pygame.draw.rect(surf, R.GLYPH_GLOW, box, 2)

        display = current_text
        if blink_on:
            display += "_"
        text = self.font_big.render(display, True, R.BONE)
        surf.blit(text, (box.centerx - text.get_width() // 2,
                         box.centery - text.get_height() // 2))

        # Hints.
        hint1 = self.font_sm.render(
            f"Up to {max_len} letters. Backspace to erase. Enter to confirm.",
            True, R.SAND_LIGHT,
        )
        surf.blit(hint1, (SCREEN_W // 2 - hint1.get_width() // 2, 320))
        hint2 = self.font_xs.render(
            "(Your scores are uploaded to a public global leaderboard.)",
            True, R.STONE_LIGHT,
        )
        surf.blit(hint2, (SCREEN_W // 2 - hint2.get_width() // 2, 348))
