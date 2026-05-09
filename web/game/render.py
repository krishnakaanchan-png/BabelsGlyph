"""Color palette, draw helpers, PyInstaller-safe resource path."""
from __future__ import annotations
import math
import os
import sys

import pygame

# Ancient palette.
SANDSTONE     = (216, 179, 117)
SANDSTONE_D   = (168, 132, 80)
SAND_LIGHT    = (236, 206, 152)
SKY_DAWN_TOP  = (252, 218, 158)
SKY_DAWN_BOT  = (210, 130, 90)
SKY_FORGE_TOP = (90, 50, 60)
SKY_FORGE_BOT = (200, 80, 50)
SKY_WORK_TOP  = (170, 200, 220)
SKY_WORK_BOT  = (220, 220, 200)
LAPIS         = (28, 74, 138)
LAPIS_LIGHT   = (60, 120, 200)
COPPER        = (184, 115, 51)
COPPER_LIGHT  = (220, 160, 90)
EMBER         = (255, 122, 43)
EMBER_DIM     = (180, 70, 20)
STONE         = (90, 78, 64)
STONE_DARK    = (52, 45, 38)
STONE_LIGHT   = (140, 122, 100)
BONE          = (236, 220, 188)
BLOOD         = (170, 40, 40)
GLYPH_GLOW    = (255, 210, 110)
GLYPH_GLOW_S  = (255, 244, 180)
BEAM_CORE     = (255, 240, 200)
CHARGE_FULL   = (110, 220, 130)
CHARGE_LOW    = (220, 80, 60)
HEART_RED     = (220, 60, 70)
GEAR_BRONZE   = (180, 120, 60)
GEAR_BRONZE_D = (110, 70, 30)
STEAM_WHITE   = (240, 240, 240)
PARCHMENT     = (228, 208, 160)
INK           = (60, 40, 30)
WORKSHOP_GREEN= (80, 130, 90)


def resource_path(rel: str) -> str:
    """Resolve a path that works both in dev and inside a PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__) + "/.."))
    return os.path.join(base, rel)


def lerp_color(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


# ============================================================================
# Post-processing helpers (bloom + vignette).
#
# Both helpers operate on the logical render surface so their cost scales
# with SCREEN_W x SCREEN_H, NOT with the actual window size. They look
# identical regardless of RENDER_SCALE because they run before the final
# upscale to the OS window.
# ============================================================================

def make_vignette(w: int, h: int,
                  *, strength: int = 170, falloff: float = 2.2) -> pygame.Surface:
    """Build a radial corner-darkening overlay (call once at startup).

    Internally we paint a tiny 96x96 alpha gradient and let smoothscale do
    the heavy lifting; per-pixel set_at on the full-size surface would be
    too slow on the web build.
    """
    small_n = 96
    g = pygame.Surface((small_n, small_n), pygame.SRCALPHA)
    cx = (small_n - 1) / 2.0
    cy = (small_n - 1) / 2.0
    max_d = math.hypot(cx, cy)
    for y in range(small_n):
        for x in range(small_n):
            d = math.hypot(x - cx, y - cy) / max_d
            a = int(min(255, max(0, (d ** falloff) * strength)))
            g.set_at((x, y), (0, 0, 0, a))
    return pygame.transform.smoothscale(g, (w, h))


def apply_bloom(frame: pygame.Surface, *,
                downsample: int = 4, blur_radius: int = 6,
                intensity: int = 70) -> None:
    """Add a soft bloom glow in-place on `frame`.

    Pipeline: downsample -> box-blur -> pre-multiply by intensity ->
    upscale -> additively composite back onto `frame`. Because the source
    is multiplied by intensity/255 before the additive blend, bright
    pixels (glyphs, charge, embers) gain a visible halo while dark pixels
    contribute almost nothing - that's the look we want.

    Cost is proportional to (frame_size / downsample**2). With the
    defaults below at 960x544 / down=4, the blurred buffer is 240x136
    which is essentially free on modern CPUs and on emscripten.
    """
    if intensity <= 0:
        return
    w, h = frame.get_size()
    sw = max(1, w // downsample)
    sh = max(1, h // downsample)
    small = pygame.transform.smoothscale(frame, (sw, sh))
    # box_blur was added in pygame-ce 2.4; available in pygbag 0.9.3.
    try:
        blurred = pygame.transform.box_blur(small, blur_radius)
    except (AttributeError, ValueError):
        # Cheap fallback: smoothscale-down then up to fake a blur.
        tiny = pygame.transform.smoothscale(small, (max(1, sw // 2), max(1, sh // 2)))
        blurred = pygame.transform.smoothscale(tiny, (sw, sh))
    # Pre-multiply the blur by `intensity / 255` so additive composition
    # adds at most `intensity` to any given channel.
    mul = pygame.Surface(blurred.get_size()).convert()
    mul.fill((intensity, intensity, intensity))
    blurred.blit(mul, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    up = pygame.transform.smoothscale(blurred, (w, h))
    frame.blit(up, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
