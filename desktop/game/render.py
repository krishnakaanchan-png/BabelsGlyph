"""Color palette, draw helpers, PyInstaller-safe resource path."""
from __future__ import annotations
import os
import sys

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
