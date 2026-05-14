"""Heads-up display."""
from __future__ import annotations
import math
import random
import pygame

from .constants import SCREEN_W, SCREEN_H
from . import render as R
from . import fonts


ZONE_NAMES = ["Sandstone Outskirts", "Da Vinci's Forge", "Sky Workshop"]

# ---------------------------------------------------------------------------
# Title screen — driven by a single composed background PNG (assets/title_screen.png).
# Only the dynamic / clickable parts are overlaid:
#   - menu items (text + selection highlight) over the baked menu plaque
#   - top-runs rows (live name + distance) over the baked board rows
#
# Rect coordinates below are in the TITLE PNG's native pixel space (1536x1024).
# `_title_to_screen` translates them to the on-screen contain-scaled rect.
# ---------------------------------------------------------------------------
TITLE_IMG_W = 1536
TITLE_IMG_H = 1024

# Five Top-Runs rows. Coords measured against assets/title_screen.png (1536x1024).
TITLE_BOARD_PNG_RECTS = (
    pygame.Rect(1090, 655, 335, 48),
    pygame.Rect(1090, 713, 335, 48),
    pygame.Rect(1090, 771, 335, 48),
    pygame.Rect(1090, 829, 335, 48),
    pygame.Rect(1090, 887, 335, 48),
)

# Backwards-compatible aliases so other places in the file keep working.
TITLE_SAFE = 32

# 9-slice tables retained for in-game HUD use elsewhere.
UI_PANEL_RECTS = {
    "side_panel":  (254, 678, 514, 186),
    "menu_panel":  (254, 678, 514, 186),
    "menu_button": (312, 922, 350, 56),
    "wide_button": (235, 529, 542, 82),
    "gold_button": (312, 922, 350, 56),
}

UI_PANEL_SLICES = {
    "side_panel":  ((86, 54, 106, 54), (28, 22, 34, 22)),
    "menu_panel":  ((86, 54, 106, 54), (30, 24, 36, 24)),
    "menu_button": ((62, 20, 62, 20), (24, 12, 24, 12)),
    "wide_button": ((76, 28, 76, 28), (38, 16, 38, 16)),
    "gold_button": ((62, 20, 62, 20), (22, 11, 22, 11)),
}

KEYCAP_RECTS = {
    "small": (360, 66, 118, 102),
    "wide": (374, 229, 348, 90),
}


class HUD:
    def __init__(self) -> None:
        self.font_xs   = fonts.body(13, weight="regular")
        self.font_sm   = fonts.body(16, weight="medium")
        self.font_md   = fonts.body(21, weight="bold")
        self.font_lg   = fonts.display(32, bold=True)
        self.font_big  = fonts.display(40, bold=True)
        self.font_huge = fonts.display(62, bold=True)
        self.font_title = fonts.display(74, bold=True)
        # Title-screen typography system (display=Cinzel, body=IBM Plex).
        self.title_head  = fonts.display(15, bold=True)   # panel headings
        self.title_menu  = fonts.display(18, bold=True)   # menu item label
        self.title_body  = fonts.body(13, weight="medium")
        self.title_small = fonts.body(11, weight="regular")
        self.title_tag   = fonts.display(14, bold=False)  # tagline
        # Hit-rects for the audio mute buttons (set during draw_audio_buttons).
        self.music_btn_rect: pygame.Rect | None = None
        self.sfx_btn_rect: pygame.Rect | None = None

    def _panel(self, surf, rect: pygame.Rect, *, border=R.GLYPH_GLOW,
               fill=(20, 16, 12, 170), inner=True):
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill(fill)
        surf.blit(bg, rect.topleft)
        pygame.draw.rect(surf, border, rect, 1)
        if inner and rect.width > 8 and rect.height > 8:
            pygame.draw.rect(surf, R.STONE_DARK, rect.inflate(-6, -6), 1)

    def _title_panel(self, surf, rect: pygame.Rect, kind: str = "side_panel", *, content: bool = True):
        source = UI_PANEL_RECTS.get(kind, UI_PANEL_RECTS["side_panel"])
        src_border, dst_border = UI_PANEL_SLICES.get(kind, UI_PANEL_SLICES["side_panel"])
        shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 118), shadow.get_rect(), border_radius=8)
        surf.blit(shadow, (rect.x + 4, rect.y + 7))
        if not R.draw_atlas_9slice(surf, "ui_panels.png", source, rect, src_border, dst_border):
            R.carved_panel(surf, rect, fill=(44, 25, 14, 218), border=R.TITLE_GOLD_D)
        if content:
            inset_x = max(20, min(34, rect.width // 8))
            inset_y = max(18, min(30, rect.height // 7))
            inner = rect.inflate(-inset_x * 2, -inset_y * 2)
            well = pygame.Surface(inner.size, pygame.SRCALPHA)
            well.fill((17, 10, 6, 144))
            surf.blit(well, inner.topleft)
            pygame.draw.rect(surf, (156, 92, 35), inner, 1)

    def _center_text(self, surf, font, text, center, color=R.BONE, shadow=True):
        img = font.render(text, True, color)
        pos = (center[0] - img.get_width() // 2, center[1] - img.get_height() // 2)
        self._text(surf, font, text, pos, color=color, shadow=shadow)
        return img.get_rect(center=center)

    def _draw_keycap(self, surf, label: str, rect: pygame.Rect):
        source = KEYCAP_RECTS["wide" if rect.width > 58 else "small"]
        cap_src = R.get_atlas_region("ui_keycaps.png", source)
        if cap_src is not None:
            surf.blit(pygame.transform.smoothscale(cap_src, rect.size), rect.topleft)
        else:
            cap = pygame.Surface(rect.size, pygame.SRCALPHA)
            cap.fill((30, 17, 9, 230))
            surf.blit(cap, rect.topleft)
            pygame.draw.rect(surf, R.TITLE_GOLD_D, rect, 2)
            pygame.draw.rect(surf, R.GLYPH_GLOW, rect.inflate(-5, -5), 1)
        txt = self.title_small.render(label.upper(), True, R.TITLE_GOLD_HI)
        surf.blit(txt, (rect.centerx - txt.get_width() // 2,
                        rect.centery - txt.get_height() // 2))

    def _draw_key_group(self, surf, keys: list[str], x: int, y: int) -> int:
        cursor = x
        for key in keys:
            width = 64 if len(key) > 3 else 30
            self._draw_keycap(surf, key, pygame.Rect(cursor, y, width, 22))
            cursor += width + 4
        return cursor

    def _heading(self, surf, text: str, pos: tuple[int, int]) -> None:
        # Warm-gold heading with subtle ink shadow + soft highlight ghost.
        sh = self.title_head.render(text.upper(), True, R.TITLE_INK)
        surf.blit(sh, (pos[0] + 1, pos[1] + 1))
        body = self.title_head.render(text.upper(), True, R.TITLE_GOLD_HI)
        surf.blit(body, pos)

    def _online_badge(self, surf, text: str, rect: pygame.Rect) -> None:
        # Themed copper/gold pill (no neon green) using the gold_button frame.
        self._title_panel(surf, rect, "gold_button", content=False)
        img = self.title_small.render(text.upper(), True, R.TITLE_INK)
        surf.blit(img, (rect.centerx - img.get_width() // 2,
                        rect.centery - img.get_height() // 2))

    def _draw_motes(self, surf, t: float):
        rng = random.Random(953)
        for i in range(52):
            x = (rng.randrange(SCREEN_W) + int(t * (8 + i % 9))) % SCREEN_W
            base_y = rng.randrange(70, SCREEN_H - 34)
            y = base_y + int(8 * math.sin(t * 0.8 + i))
            alpha = 40 + int(35 * (1 + math.sin(t * 1.7 + i * 0.9)))
            pygame.draw.circle(surf, (*R.GLYPH_GLOW, alpha), (x, y), 1)

    # ------------------------------------------------------------------
    # Title — composed PNG background + minimal dynamic overlays.
    # ------------------------------------------------------------------
    def _title_image_rect(self) -> pygame.Rect:
        """Return the on-screen rect where the title PNG is drawn (contain-fit)."""
        scale = SCREEN_H / TITLE_IMG_H
        w = int(round(TITLE_IMG_W * scale))
        h = SCREEN_H
        x = (SCREEN_W - w) // 2
        return pygame.Rect(x, 0, w, h)

    def _title_to_screen(self, png_rect: pygame.Rect) -> pygame.Rect:
        """Translate a rect from PNG-native coords to on-screen coords."""
        img = self._title_image_rect()
        sx = img.width / TITLE_IMG_W
        sy = img.height / TITLE_IMG_H
        return pygame.Rect(
            img.x + int(round(png_rect.x * sx)),
            img.y + int(round(png_rect.y * sy)),
            max(1, int(round(png_rect.w * sx))),
            max(1, int(round(png_rect.h * sy))),
        )

    def _board_screen_rects(self) -> list[pygame.Rect]:
        return [self._title_to_screen(r) for r in TITLE_BOARD_PNG_RECTS]

    def _draw_overlay_board(self, surf, scores, *, highlight_name: str | None):
        rects = self._board_screen_rects()
        scores = (scores or [])[:5]
        for i, br in enumerate(rects):
            radius = max(4, br.height // 3)
            plate = pygame.Surface(br.size, pygame.SRCALPHA)
            pygame.draw.rect(plate, (20, 13, 8, 255), plate.get_rect(),
                             border_radius=radius)
            surf.blit(plate, br.topleft)
            pygame.draw.rect(surf, (180, 130, 60), br, width=1,
                             border_radius=radius)
            if i >= len(scores):
                dot_color = (200, 160, 90)
                cy = br.centery
                for dx in (-10, 0, 10):
                    pygame.draw.circle(surf, dot_color,
                                       (br.centerx + dx, cy), 2)
                continue
            score = scores[i]
            name = str(score.get("name", "?"))[:12]
            dist = int(score.get("distance_m", 0))
            is_me = (highlight_name and name == highlight_name)
            num_color = R.TITLE_GOLD_HI
            name_color = R.GLYPH_GLOW if is_me else R.BONE
            dist_color = R.SAND_LIGHT
            # Number.
            num_img = self.title_body.render(f"{i + 1}.", True, num_color)
            num_sh  = self.title_body.render(f"{i + 1}.", True, R.TITLE_INK)
            ny = br.centery - num_img.get_height() // 2
            surf.blit(num_sh, (br.x + 9, ny + 1))
            surf.blit(num_img, (br.x + 8, ny))
            # Name.
            nm_img = self.title_body.render(name, True, name_color)
            nm_sh  = self.title_body.render(name, True, R.TITLE_INK)
            surf.blit(nm_sh, (br.x + 35, ny + 1))
            surf.blit(nm_img, (br.x + 34, ny))
            # Distance (right-aligned).
            d_text = f"{dist}m"
            d_img = self.title_body.render(d_text, True, dist_color)
            d_sh  = self.title_body.render(d_text, True, R.TITLE_INK)
            dx = br.right - d_img.get_width() - 10
            surf.blit(d_sh, (dx + 1, ny + 1))
            surf.blit(d_img, (dx, ny))

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
        music_icon = R.get_sheet_frame("ui_audio_icons.png", 2, 2, 1 if music_muted else 0)
        sfx_icon = R.get_sheet_frame("ui_audio_icons.png", 2, 2, 3 if sfx_muted else 2)
        if music_icon is not None:
            surf.blit(pygame.transform.smoothscale(music_icon, (18, 18)), (m_rect.x + 3, m_rect.y + 2))
        else:
            self._draw_note_icon(surf, m_rect.centerx, m_rect.centery, music_muted, col_m)
        if sfx_icon is not None:
            surf.blit(pygame.transform.smoothscale(sfx_icon, (18, 18)), (s_rect.x + 3, s_rect.y + 2))
        else:
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
                   gamepad_connected: bool = False,
                   name_prompt: str | None = None,
                   blink_on: bool = True):
        # 1) Letterbox/clear background, then blit the composed title PNG.
        surf.fill((10, 7, 5))
        img_rect = self._title_image_rect()
        title_img = R.get_scaled_asset("title_screen.png", img_rect.width, img_rect.height,
                                       alpha=False, cover=False)
        if title_img is not None:
            surf.blit(title_img, img_rect.topleft)
        else:
            # Fallback if the asset is missing: legacy background.
            surf.blit(R.get_title_background(SCREEN_W, SCREEN_H), (0, 0))

        t = pygame.time.get_ticks() / 1000.0

        # 2) Dynamic overlay — just the top-runs rows.
        self._draw_overlay_board(surf, scores or [], highlight_name=player_name)

        # 3) Inline name-entry prompt (only when no profile name is saved).
        if name_prompt is not None:
            self._draw_name_prompt(surf, name_prompt, blink_on)

    def _draw_name_prompt(self, surf, text: str, blink_on: bool, max_len: int = 12):
        """Small themed panel asking for the player's name on the title screen.
        Sits dead-center so it covers the baked 'PRESS SPACE TO START' call-to-action
        until the name has been inscribed."""
        w, h = 360, 84
        rect = pygame.Rect((SCREEN_W - w) // 2, (SCREEN_H - h) // 2 + 40, w, h)
        radius = 10
        plate = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(plate, (20, 13, 8, 240), plate.get_rect(), border_radius=radius)
        surf.blit(plate, rect.topleft)
        pygame.draw.rect(surf, (180, 130, 60), rect, width=1, border_radius=radius)

        label = self.title_tag.render("INSCRIBE THY NAME", True, R.TITLE_GOLD_HI)
        surf.blit(label, (rect.centerx - label.get_width() // 2, rect.y + 8))

        shown = (text or "")[:max_len]
        caret = "_" if blink_on else " "
        name_img = self.font_md.render(shown + caret, True, R.BONE)
        surf.blit(name_img,
                  (rect.centerx - name_img.get_width() // 2, rect.y + 28))

        hint = self.font_xs.render("ENTER to confirm", True, (200, 160, 90))
        surf.blit(hint,
                  (rect.centerx - hint.get_width() // 2,
                   rect.bottom - hint.get_height() - 6))

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
