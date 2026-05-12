"""Font loading with bundled TTFs.

Loads two open-licensed typefaces from `assets/fonts/`:

- **Cinzel**: display face for headings and titles.
- **IBM Plex Sans**: body face for HUD and leaderboard text.

Falls back to pygame's default font if a TTF is missing so gameplay continues.
"""
from __future__ import annotations

import os
import pygame


_FONT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, "assets", "fonts")
)


def _path(name: str) -> str:
    return os.path.join(_FONT_DIR, name)


def load(name: str, size: int) -> pygame.font.Font:
    """Load a bundled TTF and gracefully fall back to the default font."""
    p = _path(name)
    try:
        if os.path.isfile(p):
            return pygame.font.Font(p, size)
    except Exception:
        pass
    return pygame.font.Font(None, size)


def display(size: int, *, bold: bool = True) -> pygame.font.Font:
    """Cinzel for titles and prominent labels."""
    return load("Cinzel-Bold.ttf" if bold else "Cinzel-Regular.ttf", size)


def body(size: int, *, weight: str = "regular") -> pygame.font.Font:
    """IBM Plex Sans for body and UI text."""
    fname = {
        "regular": "IBMPlexSans-Regular.ttf",
        "medium": "IBMPlexSans-Medium.ttf",
        "bold": "IBMPlexSans-Bold.ttf",
    }.get(weight, "IBMPlexSans-Regular.ttf")
    return load(fname, size)
