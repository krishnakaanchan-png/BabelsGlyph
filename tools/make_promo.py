"""Render a 30-second cinematic launch-trailer for Babel's Glyph.

Drives the live game in headless mode with an autopilot, then layers a
trailer-grade post-FX stack on top:

* Multi-act timeline with hard cuts on beats
* Time-scaled simulation (slow-mo intros / speed-ramp climax / final slam)
* White flashes + camera shake on every beat cut
* Chromatic aberration on dashes & climax
* Animated color-grade per scene (cold blue -> warm gold -> red climax)
* Letterbox bars that animate in/out
* Subtle scanlines + radial vignette
* Title styles: fade, slam, lower-third, zone reveal, glitch, logo slam, CTA
* Animated arcane-glyph rune for the cold-open
* Particle burst for the final logo slam

Output: BabelsGlyph_Promo.mp4 in the workspace root.
"""
from __future__ import annotations

import math
import os
import random
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pygame
import imageio.v2 as imageio

from game.constants import SCREEN_W, SCREEN_H, TILE
from game import particles
from game import render as R
from game.input import Input
from game.player import Player
from game.world import World
from game.entities import EntityManager
from game.chunks import Chunks


# ---------------------------------------------------------------------------
# Trailer config
# ---------------------------------------------------------------------------
DURATION_S = 30.0
FPS = 60
TOTAL_FRAMES = int(DURATION_S * FPS)
OUT_PATH = ROOT / "BabelsGlyph_Promo.mp4"
SILENT_VIDEO_PATH = ROOT / "BabelsGlyph_Promo_silent.mp4"
AUDIO_PATH = ROOT / "BabelsGlyph_Promo_audio.wav"

# Hard cuts — each gets a white flash + camera-shake punch.
BEATS = [2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0, 22.5, 25.0, 28.0]


# ---------------------------------------------------------------------------
# Beat / scene timing functions
# ---------------------------------------------------------------------------
def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def time_scale(t: float) -> float:
    """Multiplier on physics dt — used for slow-mo & speed ramps."""
    if t < 2.5:  return 0.85   # running invisibly behind cold-open curtain
    if t < 5.0:  return 0.55   # post-slam slow-mo intro
    if t < 13.0: return 1.00
    if t < 20.0: return 1.18   # zone tour, picking up
    if t < 25.0: return 1.45   # climax
    if t < 26.5: return 0.55   # final slam slow-mo
    return 1.0


def beat_pulse(t: float, half_life: float = 0.18) -> float:
    """0..1 envelope — fires on each BEATS entry, decays quickly."""
    best = 0.0
    for b in BEATS:
        if t >= b and t - b < half_life * 2:
            v = max(0.0, 1.0 - (t - b) / half_life)
            best = max(best, v)
    return best


def chroma_strength(t: float, dashing: bool) -> float:
    s = 0.0
    if dashing:
        s = 0.7
    if 22.0 <= t < 25.5:        # red climax push
        s = max(s, 0.55)
    if 25.0 <= t < 26.0:        # extra punch on final logo slam
        s = max(s, 0.9)
    return s


def letterbox_h(t: float) -> int:
    if t < 0.6:
        return int(54 * smoothstep(t / 0.6))
    if t > 29.4:
        return int(54 * smoothstep((30.0 - t) / 0.6))
    return 54


def grade_color(t: float) -> tuple[int, int, int, int]:
    """Translucent color overlay, scene-by-scene."""
    if t < 2.5:  return (8, 12, 24, 230)     # cold-open: near black-blue
    if t < 5.0:  return (240, 200, 120, 32)  # warm punch right after slam
    if t < 13.0: return (0, 0, 0, 0)
    if t < 20.0: return (255, 200, 110, 22)  # zone tour: warm gold tint
    if t < 25.5: return (210, 60, 40, 40)    # climax: red urgency
    if t < 28.0: return (255, 220, 140, 24)
    return (0, 0, 0, 0)


def cold_open_alpha(t: float) -> float:
    """Black curtain that hides the running game until the first slam."""
    if t < 2.05:
        return 1.0
    if t < 2.5:
        return 1.0 - smoothstep((t - 2.05) / 0.45)
    return 0.0


# ---------------------------------------------------------------------------
# Scripted title cards
#   (start, end, big, small, style)
# ---------------------------------------------------------------------------
TIMELINE: list[tuple[float, float, str, str, str]] = [
    (0.0,  2.5,  "SOME RUINS",          "remember everything",                  "fade"),
    (2.5,  5.0,  "BABEL'S GLYPH",       "an endless run through ancient tech",  "slam"),
    (5.0,  7.5,  "OUTRUN HISTORY",      "the past is collapsing behind you",    "lower"),
    (7.5,  10.0, "PARKOUR THE PAST",    "double-jump  ·  dash  ·  wall-slide",  "lower"),
    (10.0, 12.5, "STRIKE WITH GLYPHS",  "hurl glyph-bombs  ·  stomp automatons","lower"),
    (12.5, 15.0, "SANDSTONE OUTSKIRTS", "ZONE 01",                              "zone"),
    (15.0, 17.5, "DA VINCI'S FORGE",    "ZONE 02",                              "zone"),
    (17.5, 20.0, "SKY WORKSHOP",        "ZONE 03",                              "zone"),
    (20.0, 22.5, "DODGE EVERYTHING",    "spikes · steam · crumble · arrows",    "glitch"),
    (22.5, 25.0, "WRITE YOUR LEGEND",   "every run rewrites the past",          "lower"),
    (25.0, 28.0, "BABEL'S GLYPH",       "available now",                        "slam_logo"),
    (28.0, 30.0, "PLAY  NOW",           "press SPACE to begin",                 "cta"),
]


# ---------------------------------------------------------------------------
# Autopilot — keeps the run highlight-reel-worthy
# ---------------------------------------------------------------------------
class Autopilot:
    def __init__(self, seed: int = 11) -> None:
        self.rng = random.Random(seed)
        self.t = 0.0
        self._next_jump = 0.25
        self._next_dash = 1.4
        self._next_bomb = 3.0
        self._next_slide = 5.0
        self._slide_until = -1.0

    def step(self, dt: float, inp: Input, player: Player, scene_t: float) -> None:
        self.t += dt
        inp.begin_frame()
        inp.right = True
        inp.left = False
        inp.down = self.t < self._slide_until

        # Climax: more aggressive — faster jump cadence, more dashes.
        is_climax = scene_t >= 20.0
        jump_min = 0.30 if is_climax else 0.45
        jump_max = 0.70 if is_climax else 0.85
        dash_min = 0.9 if is_climax else 1.6
        dash_max = 1.5 if is_climax else 2.4

        if self.t >= self._next_jump:
            if player.on_ground:
                inp.jump_pressed = True
                self._next_jump = self.t + self.rng.uniform(jump_min, jump_max)
            elif player.vy > 60 and self.rng.random() < 0.55:
                inp.jump_pressed = True   # double-jump for air time
                self._next_jump = self.t + self.rng.uniform(0.55, 0.95)

        if self.t >= self._next_dash:
            inp.dash_pressed = True
            self._next_dash = self.t + self.rng.uniform(dash_min, dash_max)

        if self.t >= self._next_bomb:
            inp.bomb_pressed = True
            self._next_bomb = self.t + self.rng.uniform(2.6, 4.2)

        if self.t >= self._next_slide and player.on_ground and not is_climax:
            self._slide_until = self.t + 0.32
            self._next_slide = self.t + self.rng.uniform(4.0, 6.0)


# ---------------------------------------------------------------------------
# Pre-built static overlay textures
# ---------------------------------------------------------------------------
def build_vignette() -> pygame.Surface:
    s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    cx, cy = SCREEN_W * 0.5, SCREEN_H * 0.55
    max_d = math.hypot(cx, cy)
    step = 8
    for y in range(0, SCREEN_H, step):
        for x in range(0, SCREEN_W, step):
            d = math.hypot(x - cx, y - cy) / max_d
            a = int(min(190, max(0, (d - 0.55) * 400)))
            if a > 0:
                pygame.draw.rect(s, (0, 0, 0, a), (x, y, step, step))
    return s


def build_scanlines() -> pygame.Surface:
    s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for y in range(0, SCREEN_H, 3):
        pygame.draw.line(s, (0, 0, 0, 28), (0, y), (SCREEN_W, y))
    return s


# ---------------------------------------------------------------------------
# FX state — particle burst, fonts, helpers
# ---------------------------------------------------------------------------
class Fx:
    def __init__(self) -> None:
        self.f_xs   = pygame.font.SysFont("consolas", 14, bold=True)
        self.f_sm   = pygame.font.SysFont("consolas", 18)
        self.f_md   = pygame.font.SysFont("consolas", 24, bold=True)
        self.f_lg   = pygame.font.SysFont("consolas", 38, bold=True)
        self.f_xl   = pygame.font.SysFont("consolas", 56, bold=True)
        self.f_huge = pygame.font.SysFont("consolas", 92, bold=True)
        self.vignette = build_vignette()
        self.scanlines = build_scanlines()
        self.burst: list[list[float]] = []
        self._spawned: set[str] = set()

    # Spawn a radial burst at scripted moments.
    def maybe_spawn_burst(self, t: float) -> None:
        for key, when, n in (("logo", 25.0, 160), ("cta", 28.0, 70)):
            if t >= when and key not in self._spawned:
                self._spawned.add(key)
                cx, cy = SCREEN_W * 0.5, SCREEN_H * 0.5
                for _ in range(n):
                    a = random.random() * math.tau
                    sp = random.uniform(160, 540)
                    self.burst.append([cx, cy,
                                       math.cos(a) * sp, math.sin(a) * sp,
                                       0.0,
                                       random.uniform(0.7, 1.6),
                                       random.uniform(2.0, 5.5)])

    def update_burst(self, dt: float) -> None:
        for p in self.burst:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 320.0 * dt
            p[2] *= 0.985
            p[4] += dt
        self.burst = [p for p in self.burst if p[4] < p[5]]

    def draw_burst(self, surf: pygame.Surface) -> None:
        for x, y, _vx, _vy, age, life, size in self.burst:
            tt = age / life
            a = max(0, int(255 * (1 - tt)))
            r = max(1, int(size * (1 - tt * 0.3)))
            blob = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(blob, (255, 220, 130, a), (r + 2, r + 2), r)
            pygame.draw.circle(blob, (255, 255, 220, min(255, a + 80)),
                               (r + 2, r + 2), max(1, r - 2))
            surf.blit(blob, (x - r - 2, y - r - 2))


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def card_alpha(t: float, s: float, e: float,
               fade_in: float = 0.4, fade_out: float | None = None) -> float:
    fo = fade_out if fade_out is not None else fade_in
    if t < s + fade_in:
        return smoothstep((t - s) / fade_in)
    if t > e - fo:
        return smoothstep((e - t) / fo)
    return 1.0


def draw_centered(surf: pygame.Surface, font: pygame.font.Font, text: str,
                  y: int, color, alpha: float, scale: float = 1.0) -> None:
    if alpha <= 0:
        return
    img = font.render(text, True, color)
    if abs(scale - 1.0) > 0.01:
        w = max(1, int(img.get_width() * scale))
        h = max(1, int(img.get_height() * scale))
        img = pygame.transform.smoothscale(img, (w, h))
    shadow = font.render(text, True, (0, 0, 0))
    if abs(scale - 1.0) > 0.01:
        shadow = pygame.transform.smoothscale(shadow, img.get_size())
    shadow.set_alpha(int(180 * alpha))
    img.set_alpha(int(255 * alpha))
    x = SCREEN_W // 2 - img.get_width() // 2
    surf.blit(shadow, (x + 3, y + 3))
    surf.blit(img, (x, y))


def draw_glyph_rune(surf: pygame.Surface, t: float, alpha: float) -> None:
    """Animated arcane glyph used during the cold open."""
    if alpha <= 0:
        return
    cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 20
    pulse = 0.5 + 0.5 * math.sin(t * 1.4)
    r = 70 + int(8 * pulse)

    # Outer glow halo.
    g_size = (r + 70) * 2
    glow = pygame.Surface((g_size, g_size), pygame.SRCALPHA)
    gc = g_size // 2
    for i in range(6, 0, -1):
        rr = r + i * 9
        a = int(alpha * (10 + i * 5))
        pygame.draw.circle(glow, (255, 210, 110, a), (gc, gc), rr)
    surf.blit(glow, (cx - gc, cy - gc))

    # Two concentric rings.
    pygame.draw.circle(surf, (255, 220, 140), (cx, cy), r, 3)
    pygame.draw.circle(surf, (200, 160, 80), (cx, cy), r - 12, 1)

    # Spinning runic cross-hairs.
    rot = t * 28.0
    for k in range(4):
        ang = math.radians(rot + k * 90)
        dx, dy = math.cos(ang) * (r * 0.92), math.sin(ang) * (r * 0.92)
        ix, iy = math.cos(ang) * (r * 0.32), math.sin(ang) * (r * 0.32)
        pygame.draw.line(surf, (255, 220, 140),
                         (cx + ix, cy + iy), (cx + dx, cy + dy), 2)
    # Tiny dots at compass points.
    for k in range(8):
        ang = math.radians(k * 45 - rot * 0.5)
        dx, dy = math.cos(ang) * (r + 14), math.sin(ang) * (r + 14)
        pygame.draw.circle(surf, (255, 230, 160), (int(cx + dx), int(cy + dy)), 2)


def draw_trailer_hud(surf: pygame.Surface, t: float, player: Player,
                     world: World, fx: Fx) -> None:
    """Minimal HUD that reads as game footage but is trailer-clean."""
    # Hide HUD entirely during cold-open and final logo slam.
    if t < 2.5 or t >= 25.0:
        return

    # Top-left hearts.
    for i in range(player.max_hp):
        full = i < player.hp
        c = R.HEART_RED if full else R.STONE_DARK
        x = 22 + i * 22
        y = 24
        pygame.draw.circle(surf, c, (x - 4, y - 2), 5)
        pygame.draw.circle(surf, c, (x + 4, y - 2), 5)
        pygame.draw.polygon(surf, c, [(x - 8, y - 1), (x + 8, y - 1), (x, y + 8)])

    # Glyph counter.
    gx = 22 + player.max_hp * 22 + 10
    pygame.draw.circle(surf, R.GLYPH_GLOW, (gx + 8, 22), 7)
    pygame.draw.circle(surf, R.STONE_DARK, (gx + 8, 22), 7, 1)
    txt = fx.f_md.render(f"x {player.glyphs}", True, R.BONE)
    sh = fx.f_md.render(f"x {player.glyphs}", True, R.STONE_DARK)
    surf.blit(sh, (gx + 21, 13))
    surf.blit(txt, (gx + 20, 12))

    # Distance counter — top-right, large for drama.
    distance_m = int(world.distance / 50.0)
    dt_text = fx.f_lg.render(f"{distance_m:>4} m", True, R.BONE)
    dt_sh   = fx.f_lg.render(f"{distance_m:>4} m", True, R.STONE_DARK)
    surf.blit(dt_sh, (SCREEN_W - dt_text.get_width() - 18, 13))
    surf.blit(dt_text, (SCREEN_W - dt_text.get_width() - 19, 12))


# ---------------------------------------------------------------------------
# Title-card styles
# ---------------------------------------------------------------------------
def draw_card(surf: pygame.Surface, t: float, fx: Fx) -> None:
    active = None
    for entry in TIMELINE:
        s, e, *_ = entry
        if s <= t <= e:
            active = entry
            break
    if active is None:
        return
    s, e, big, small, style = active

    if style == "fade":
        a = card_alpha(t, s, e, fade_in=0.6, fade_out=0.5)
        draw_centered(surf, fx.f_lg, big, SCREEN_H // 2 - 30, R.GLYPH_GLOW, a)
        draw_centered(surf, fx.f_sm, small, SCREEN_H // 2 + 22, R.BONE, a * 0.85)

    elif style == "slam":
        a = card_alpha(t, s, e, fade_in=0.25, fade_out=0.5)
        scale = 2.6 - 1.6 * smoothstep(min(1.0, (t - s) / 0.45))
        draw_centered(surf, fx.f_huge, big, SCREEN_H // 2 - 60,
                      R.GLYPH_GLOW, a, scale=scale)
        sub_a = smoothstep(min(1.0, (t - s - 0.5) / 0.4))
        sub_a *= 1.0 - smoothstep(max(0.0, (t - e + 0.4) / 0.4))
        draw_centered(surf, fx.f_sm, small, SCREEN_H // 2 + 38, R.BONE, sub_a)

    elif style == "lower":
        slide_in  = smoothstep(min(1.0, (t - s) / 0.35))
        slide_out = 1.0 - smoothstep(max(0.0, (t - e + 0.35) / 0.35))
        a = slide_in * slide_out
        if a <= 0:
            return
        big_img = fx.f_md.render(big, True, R.BONE)
        sm_img  = fx.f_xs.render(small, True, R.GLYPH_GLOW)
        pad = 14
        w = max(big_img.get_width(), sm_img.get_width()) + pad * 2 + 10
        h = big_img.get_height() + sm_img.get_height() + pad + 6
        x_target = 60
        x = int(-w + (x_target + w) * (slide_in if t < e - 0.35 else slide_out))
        y = SCREEN_H - 130
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((20, 16, 12, int(195 * a)))
        surf.blit(bg, (x, y))
        pygame.draw.rect(surf, (255, 210, 110), (x, y, 4, h))
        big_img.set_alpha(int(255 * a))
        sm_img.set_alpha(int(255 * a))
        surf.blit(big_img, (x + pad + 8, y + 6))
        surf.blit(sm_img,  (x + pad + 8, y + 6 + big_img.get_height() + 2))

    elif style == "zone":
        a = card_alpha(t, s, e, fade_in=0.3, fade_out=0.4)
        y_mid = SCREEN_H // 2
        line_w = int(280 * a)
        pygame.draw.line(surf, (255, 210, 110),
                         (SCREEN_W // 2 - line_w, y_mid - 50),
                         (SCREEN_W // 2 + line_w, y_mid - 50), 2)
        draw_centered(surf, fx.f_sm, small, y_mid - 38, R.GLYPH_GLOW, a)
        draw_centered(surf, fx.f_lg, big, y_mid - 18, R.BONE, a)
        pygame.draw.line(surf, (255, 210, 110),
                         (SCREEN_W // 2 - line_w, y_mid + 30),
                         (SCREEN_W // 2 + line_w, y_mid + 30), 2)

    elif style == "glitch":
        a = card_alpha(t, s, e, fade_in=0.3, fade_out=0.4)
        jitter = int(math.sin(t * 73.0) * 3)
        # Red & cyan offset ghosts behind the white text.
        for col, dx in ((R.BLOOD, -3), ((90, 200, 255), 3)):
            img = fx.f_lg.render(big, True, col)
            img.set_alpha(int(180 * a))
            surf.blit(img, (SCREEN_W // 2 - img.get_width() // 2 + dx + jitter,
                            SCREEN_H // 2 - 30))
        draw_centered(surf, fx.f_lg, big, SCREEN_H // 2 - 30, R.BONE, a)
        draw_centered(surf, fx.f_sm, small, SCREEN_H // 2 + 22, R.GLYPH_GLOW, a * 0.9)

    elif style == "slam_logo":
        a = card_alpha(t, s, e, fade_in=0.25, fade_out=0.4)
        scale = 3.0 - 2.0 * smoothstep(min(1.0, (t - s) / 0.5))
        draw_centered(surf, fx.f_huge, big, SCREEN_H // 2 - 60,
                      R.GLYPH_GLOW, a, scale=scale)
        sub_a = smoothstep(min(1.0, (t - s - 0.6) / 0.5))
        sub_a *= 1.0 - smoothstep(max(0.0, (t - e + 0.4) / 0.4))
        draw_centered(surf, fx.f_md, small, SCREEN_H // 2 + 50, R.BONE, sub_a)

    elif style == "cta":
        a = card_alpha(t, s, e, fade_in=0.35, fade_out=0.3)
        draw_centered(surf, fx.f_xl, big, SCREEN_H // 2 - 30, R.GLYPH_GLOW, a)
        pulse = 0.5 + 0.5 * math.sin(t * 8.0)
        chip = fx.f_md.render(small, True, R.STONE_DARK)
        pad = 12
        w = chip.get_width() + pad * 2
        h = chip.get_height() + pad
        x = SCREEN_W // 2 - w // 2
        y = SCREEN_H // 2 + 36
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((255, 210, 110, int((190 + 60 * pulse) * a)))
        surf.blit(bg, (x, y))
        chip.set_alpha(int(255 * a))
        surf.blit(chip, (x + pad, y + pad // 2))


# ---------------------------------------------------------------------------
# Post-FX
# ---------------------------------------------------------------------------
def apply_chroma(arr: np.ndarray, strength: float) -> np.ndarray:
    """Cheap chromatic-aberration: shift R left, B right."""
    if strength <= 0.05:
        return arr
    shift = int(2 + strength * 6)   # 2..8 px
    out = arr.copy()
    out[:, shift:, 0]   = arr[:, :-shift, 0]   # R channel pushed right
    out[:, :-shift, 2]  = arr[:, shift:, 2]    # B channel pushed left
    return out


# ---------------------------------------------------------------------------
# Safety: keep autopilot player alive forever
# ---------------------------------------------------------------------------
def keep_player_safe(player: Player, world: World) -> None:
    player.hp = player.max_hp
    player.alive = True
    if player._invuln < 0.2:
        player._invuln = 0.5
    cam_x = world.camera_x
    if player.y > SCREEN_H + 200 or player.x < cam_x + 40:
        player.x = cam_x + 220.0
        player.y = 14 * TILE - 38
        player.vx = 0.0
        player.vy = 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Babel's Glyph — promo render")

    # Off-screen buffer for the raw game frame so we can shake it onto `screen`.
    game_surf = pygame.Surface((SCREEN_W, SCREEN_H)).convert()

    particles.reset()
    entities = EntityManager()
    chunks_lib = Chunks()
    world = World(chunks_lib, entities)
    world.reset()
    player = Player(120.0, 14 * TILE - 38)
    inp = Input()
    auto = Autopilot()
    fx = Fx()
    rng = random.Random(42)

    base_dt = 1.0 / FPS

    print(f"Rendering {TOTAL_FRAMES} frames at {FPS} fps -> {SILENT_VIDEO_PATH}")
    writer = imageio.get_writer(
        str(SILENT_VIDEO_PATH),
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=1,
        pixelformat="yuv420p",
    )

    try:
        for frame_idx in range(TOTAL_FRAMES):
            t = frame_idx / FPS

            for _ in pygame.event.get():
                pass

            # ---- Simulation step (with time-scaling) -----------------
            sim_dt = base_dt * time_scale(t)
            if sim_dt > 1.0 / 20.0:
                sim_dt = 1.0 / 20.0
            auto.step(sim_dt, inp, player, scene_t=t)
            world.update(sim_dt, player.x)
            player.update(sim_dt, inp, world, entities)
            entities.update_all(sim_dt, world, player)
            particles.get().update(sim_dt)
            keep_player_safe(player, world)

            # ---- Render game to off-screen buffer --------------------
            world.draw_background(game_surf)
            world.draw_tiles(game_surf)
            entities.draw_all(game_surf, world.camera_x)
            player.draw(game_surf, world.camera_x)
            particles.get().draw(game_surf, world.camera_x)

            # ---- Camera shake punch on each beat ---------------------
            pulse = beat_pulse(t)
            shake_amp = 14.0 * pulse
            # Continuous mild shake during the climax block.
            if 21.5 <= t < 25.5:
                shake_amp = max(shake_amp, 4.0)
            sx = int(rng.uniform(-shake_amp, shake_amp)) if shake_amp > 0 else 0
            sy = int(rng.uniform(-shake_amp, shake_amp)) if shake_amp > 0 else 0

            screen.fill((0, 0, 0))
            screen.blit(game_surf, (sx, sy))

            # ---- Color grade -----------------------------------------
            r, g, b, a = grade_color(t)
            if a > 0:
                tint = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                tint.fill((r, g, b, a))
                screen.blit(tint, (0, 0))

            # ---- Subtle scanlines + vignette -------------------------
            screen.blit(fx.scanlines, (0, 0))
            screen.blit(fx.vignette, (0, 0))

            # ---- Letterbox bars --------------------------------------
            lb = letterbox_h(t)
            if lb > 0:
                bar = pygame.Surface((SCREEN_W, lb))
                bar.fill((0, 0, 0))
                screen.blit(bar, (0, 0))
                screen.blit(bar, (0, SCREEN_H - lb))

            # ---- Cold-open black curtain + glyph rune ---------------
            curtain_a = cold_open_alpha(t)
            if curtain_a > 0:
                curtain = pygame.Surface((SCREEN_W, SCREEN_H))
                curtain.fill((6, 8, 14))
                curtain.set_alpha(int(255 * curtain_a))
                screen.blit(curtain, (0, 0))
            if t < 2.5:
                rune_a = smoothstep(min(1.0, (t - 0.2) / 0.8))
                rune_a *= 1.0 - smoothstep(max(0.0, (t - 2.0) / 0.5))
                draw_glyph_rune(screen, t, rune_a)

            # ---- Trailer HUD (clean, minimal) ------------------------
            draw_trailer_hud(screen, t, player, world, fx)

            # ---- Title cards -----------------------------------------
            draw_card(screen, t, fx)

            # ---- Particle bursts (logo slam, CTA) --------------------
            fx.maybe_spawn_burst(t)
            fx.update_burst(base_dt)
            fx.draw_burst(screen)

            # ---- White flash on each beat cut ------------------------
            flash_a = pulse
            # Extra-bright flash on the two big logo slams.
            if 2.5 <= t < 2.7 or 25.0 <= t < 25.25:
                flash_a = max(flash_a, 1.0 - (t - (2.5 if t < 25 else 25.0)) / 0.2)
            if flash_a > 0.01:
                flash = pygame.Surface((SCREEN_W, SCREEN_H))
                flash.fill((255, 248, 220))
                flash.set_alpha(int(220 * flash_a))
                screen.blit(flash, (0, 0))

            # ---- Watermark -------------------------------------------
            if 5.0 <= t < 27.5:
                wm = fx.f_xs.render("babel's glyph  //  endless runner",
                                    True, R.SAND_LIGHT)
                wm.set_alpha(140)
                screen.blit(wm, (12, SCREEN_H - 26))

            # ---- Capture & post-process chromatic aberration --------
            arr = pygame.surfarray.array3d(screen).swapaxes(0, 1)
            cs = chroma_strength(t, dashing=player.is_dashing)
            arr = apply_chroma(arr, cs)
            writer.append_data(arr)

            if frame_idx % 60 == 0:
                pct = 100.0 * frame_idx / TOTAL_FRAMES
                print(f"  frame {frame_idx:4d}/{TOTAL_FRAMES}  "
                      f"({pct:5.1f}%)  t={t:5.2f}s  scale={time_scale(t):.2f}")
    finally:
        writer.close()
        pygame.quit()

    # ---- Generate audio track + mux into the final MP4 ---------------------
    mux_audio_into(SILENT_VIDEO_PATH, AUDIO_PATH, OUT_PATH)

    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"Done. Wrote {OUT_PATH}  ({size_mb:.2f} MB)")


# ---------------------------------------------------------------------------
# Audio orchestration: synth music + SAPI narration, then ffmpeg mux
# ---------------------------------------------------------------------------
def mux_audio_into(silent_video: Path, audio_wav: Path, final_mp4: Path) -> None:
    """Build the audio track and mux it onto the rendered silent video.

    On any failure we keep the silent MP4 in place under `final_mp4` so the
    caller still gets a usable file.
    """
    # 1. Render audio.
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import make_audio  # type: ignore
        make_audio.render(audio_wav)
    except Exception as exc:  # noqa: BLE001
        print(f"[promo] audio synthesis failed ({exc}); keeping silent video.")
        if silent_video.exists() and not final_mp4.exists():
            silent_video.replace(final_mp4)
        return

    # 2. Find ffmpeg (bundled by imageio-ffmpeg).
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        print(f"[promo] ffmpeg unavailable ({exc}); keeping silent video.")
        if silent_video.exists() and not final_mp4.exists():
            silent_video.replace(final_mp4)
        return

    # 3. Mux.  -shortest trims to whichever stream ends first.
    if final_mp4.exists():
        try:
            final_mp4.unlink()
        except OSError:
            pass
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(silent_video),
        "-i", str(audio_wav),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(final_mp4),
    ]
    print(f"[promo] muxing audio + video -> {final_mp4}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"[promo] ffmpeg mux failed: {exc}; keeping silent video.")
        if silent_video.exists() and not final_mp4.exists():
            silent_video.replace(final_mp4)
        return

    # 4. Clean up intermediates.
    for p in (silent_video, audio_wav):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
