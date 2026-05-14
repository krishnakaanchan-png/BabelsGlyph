"""Render title-screen screenshots at 1920x1088 and 1280x720.

Usage:
    .\\.venv\\Scripts\\python.exe tools\\snap_title.py
"""
from __future__ import annotations
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1, 1))

# Make repo root importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game.constants import SCREEN_W, SCREEN_H  # noqa: E402
from game.hud import HUD  # noqa: E402

surf = pygame.Surface((SCREEN_W, SCREEN_H))
hud = HUD()
fake_scores = [
    {"name": "ENKI", "distance_m": 1842, "glyphs": 27},
    {"name": "NABU", "distance_m": 1207, "glyphs": 19},
    {"name": "ISHTAR", "distance_m":  984, "glyphs": 14},
]
hud.draw_title(surf, scores=fake_scores, player_name="ENKI", board_status="online")

out_dir = os.path.join(os.path.dirname(__file__), "..")
out_dir = os.path.abspath(out_dir)

def save(target, w, h):
    scaled = pygame.transform.smoothscale(surf, (w, h))
    pygame.image.save(scaled, target)
    print("wrote", target)

save(os.path.join(out_dir, "title_screen_cinematic_1920x1088.png"), 1920, 1088)
save(os.path.join(out_dir, "title_screen_cinematic_1280x720_check.png"), 1280, 720)
pygame.quit()
