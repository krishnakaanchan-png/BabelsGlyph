"""One-shot tool: render the ambient music to assets/music.wav.

Run this once locally; the produced WAV is committed to the repo so the
game can load it instantly at launch instead of synthesizing the loop
on every startup. Re-run any time game/music.py is changed.

Usage:
    python tools/render_music.py

Writes:
    assets/music.wav            (root tree)
    desktop/assets/music.wav    (PyInstaller build)
    web/assets/music.wav        (pygbag build)
"""
from __future__ import annotations
import os
import sys
import wave
from pathlib import Path

# Make the repo root importable regardless of how the script is invoked.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ensure pygame doesn't try to grab a real audio device.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402  (after env vars)

pygame.mixer.pre_init(22050, -16, 1, 1024)
pygame.init()

from game import music as M  # noqa: E402

TARGETS = [
    ROOT / "assets" / "music.wav",
    ROOT / "desktop" / "assets" / "music.wav",
    ROOT / "web" / "assets" / "music.wav",
]


def main() -> None:
    print(f"Rendering {M.LOOP_SEC} s of music at {M.SR} Hz mono ...")
    pcm = M._render_track()
    n_samples = len(pcm) // 2
    print(f"  -> {n_samples} samples ({n_samples / M.SR:.2f} s), {len(pcm)} bytes")

    for path in TARGETS:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(M.SR)
            w.writeframes(pcm)
        kb = path.stat().st_size / 1024
        print(f"  wrote {path}  ({kb:.1f} KB)")


if __name__ == "__main__":
    main()
