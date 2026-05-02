"""Font loading with bundled TTFs.

Loads two open-licensed typefaces from `assets/fonts/`:

- **Cinzel** — display face (Roman square capitals, evokes carved stone).
- **IBM Plex Sans** — body face (clean, modern, highly legible).

Both ship under the SIL Open Font License (see assets/fonts/OFL-*.txt).

Falls back to pygame's default font if the TTF can't be located,
so the game never crashes on a missing asset.
"""
from __future__ import annotations

import os
import pygame

# ``game/`` lives one level below the project root; assets are at <root>/assets/fonts/.
_FONT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, "assets", "fonts")
)


def _path(name: str) -> str:
    return os.path.join(_FONT_DIR, name)


def load(name: str, size: int) -> pygame.font.Font:
    """Load a bundled TTF; fall back to the built-in default if missing."""
    p = _path(name)
    try:
        if os.path.isfile(p):
            return pygame.font.Font(p, size)
    except Exception:
        pass
    # Last-resort fallback so a missing asset never crashes the game.
    return pygame.font.Font(None, size)


# Convenience accessors with curated sizes.
def display(size: int, *, bold: bool = True) -> pygame.font.Font:
    """Cinzel — for titles, big numerals, headings."""
    return load("Cinzel-Bold.ttf" if bold else "Cinzel-Regular.ttf", size)


def body(size: int, *, weight: str = "regular") -> pygame.font.Font:
    """IBM Plex Sans — for HUD readouts and instructions."""
    fname = {
        "regular": "IBMPlexSans-Regular.ttf",
        "medium":  "IBMPlexSans-Medium.ttf",
        "bold":    "IBMPlexSans-Bold.ttf",
    }.get(weight, "IBMPlexSans-Regular.ttf")
    return load(fname, size)
