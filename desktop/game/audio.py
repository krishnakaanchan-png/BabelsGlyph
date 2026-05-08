"""Procedural sound effects for Babel's Glyph.

All SFX are synthesized at startup using only the standard library
(math, array, random) — no asset files, no numpy. This keeps the
PyInstaller bundle small and makes audio fully reproducible.

Public API:
    audio.init()                     # call once after pygame is imported
    audio.get().play("jump")         # fire-and-forget
    audio.get().play("dash", vol=0.8)

If pygame.mixer cannot be initialized (e.g. headless trailer renders)
every play() call becomes a silent no-op — the game still runs.
"""
from __future__ import annotations

import array
import math
import random
from typing import Optional

import pygame


SR = 22050           # sample rate
MAX_AMP = 28000      # int16 ceiling with headroom


def _sat(x: float) -> float:
    """Soft-clip to suppress transient clicks."""
    return math.tanh(x)


def _to_pcm(samples: list[float]) -> bytes:
    arr = array.array("h")
    for s in samples:
        v = int(_sat(s) * MAX_AMP)
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        arr.append(v)
    return arr.tobytes()


def _adsr(n: int, a: float, d: float, sus: float, r: float) -> list[float]:
    """ADSR envelope. a/d/r in seconds, sus in [0,1]."""
    a_n = max(1, int(a * SR))
    d_n = max(1, int(d * SR))
    r_n = max(1, int(r * SR))
    s_n = max(0, n - a_n - d_n - r_n)
    env = [0.0] * n
    for i in range(n):
        if i < a_n:
            env[i] = i / a_n
        elif i < a_n + d_n:
            env[i] = 1.0 + (sus - 1.0) * ((i - a_n) / d_n)
        elif i < a_n + d_n + s_n:
            env[i] = sus
        else:
            t = (i - a_n - d_n - s_n) / r_n
            env[i] = sus * (1.0 - t)
    return env


def _noise(rng: random.Random, n: int, lp: float = 0.0) -> list[float]:
    """White or one-pole low-passed noise. lp in [0,1] — higher = more LP."""
    out = [0.0] * n
    state = 0.0
    for i in range(n):
        x = rng.uniform(-1.0, 1.0)
        if lp > 0:
            state = state * lp + x * (1.0 - lp)
            out[i] = state
        else:
            out[i] = x
    return out


# ---------------------------------------------------------------------------
# Per-effect synths
# ---------------------------------------------------------------------------
def _gen_jump(high: bool = False) -> bytes:
    dur = 0.11 if not high else 0.14
    n = int(SR * dur)
    f0 = 380.0 if not high else 520.0
    f1 = 760.0 if not high else 1040.0
    env = _adsr(n, 0.004, 0.025, 0.65, dur - 0.029 - 0.004)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t * t
        phase += 2 * math.pi * f / SR
        sq = 1.0 if math.sin(phase) > 0 else -1.0
        sn = math.sin(phase)
        out[i] = (0.30 * sq + 0.55 * sn) * env[i] * 0.55
    return _to_pcm(out)


def _gen_wall_jump() -> bytes:
    dur = 0.16
    n = int(SR * dur)
    rng = random.Random(7)
    env = _adsr(n, 0.002, 0.03, 0.5, dur - 0.032)
    noise = _noise(rng, n, lp=0.6)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 240 + 320 * (1 - t)
        phase += 2 * math.pi * f / SR
        click = 1.0 if i < int(0.004 * SR) else 0.0
        out[i] = (0.55 * math.sin(phase) + 0.35 * noise[i] + 0.6 * click) \
                  * env[i] * 0.55
    return _to_pcm(out)


def _gen_dash() -> bytes:
    dur = 0.20
    n = int(SR * dur)
    rng = random.Random(11)
    env = _adsr(n, 0.006, 0.05, 0.85, dur - 0.056)
    noise = _noise(rng, n, lp=0.78)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 820 - 620 * t
        phase += 2 * math.pi * f / SR
        out[i] = (0.55 * noise[i] + 0.35 * math.sin(phase)) * env[i] * 0.65
    return _to_pcm(out)


def _gen_slide() -> bytes:
    dur = 0.30
    n = int(SR * dur)
    rng = random.Random(13)
    env = _adsr(n, 0.01, 0.05, 0.6, dur - 0.06)
    noise = _noise(rng, n, lp=0.55)
    out = [0.0] * n
    for i in range(n):
        t = i / n
        trem = 0.7 + 0.3 * math.sin(2 * math.pi * 18 * t)
        out[i] = noise[i] * env[i] * trem * 0.55
    return _to_pcm(out)


def _gen_land(hard: bool) -> bytes:
    dur = 0.18 if hard else 0.10
    n = int(SR * dur)
    rng = random.Random(17 if hard else 19)
    f0 = 65.0 if hard else 95.0
    env = _adsr(n, 0.001, 0.05 if hard else 0.025, 0.0, dur - 0.051)
    noise = _noise(rng, n, lp=0.4)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        phase += 2 * math.pi * f0 / SR
        out[i] = (0.85 * math.sin(phase) + 0.30 * noise[i]) * env[i] \
                 * (0.85 if hard else 0.55)
    return _to_pcm(out)


def _gen_bomb_throw() -> bytes:
    dur = 0.18
    n = int(SR * dur)
    rng = random.Random(23)
    env = _adsr(n, 0.005, 0.03, 0.7, dur - 0.035)
    noise = _noise(rng, n, lp=0.7)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 280 + 180 * math.sin(2 * math.pi * 4 * t)
        phase += 2 * math.pi * f / SR
        out[i] = (0.45 * math.sin(phase) + 0.35 * noise[i]) * env[i] * 0.55
    return _to_pcm(out)


def _gen_explode() -> bytes:
    dur = 0.45
    n = int(SR * dur)
    rng = random.Random(29)
    env = _adsr(n, 0.001, 0.10, 0.4, dur - 0.101)
    noise = _noise(rng, n, lp=0.6)
    out = [0.0] * n
    p_lo = 0.0
    p_mid = 0.0
    for i in range(n):
        t = i / n
        f_lo = 55.0
        f_mid = 180.0 - 120.0 * t
        p_lo += 2 * math.pi * f_lo / SR
        p_mid += 2 * math.pi * f_mid / SR
        body = (0.55 * math.sin(p_lo)
                + 0.30 * math.sin(p_mid)
                + 0.55 * noise[i])
        out[i] = body * env[i] * 0.95
    return _to_pcm(out)


def _gen_hit() -> bytes:
    """Damage taken — dissonant detuned square pair."""
    dur = 0.22
    n = int(SR * dur)
    env = _adsr(n, 0.002, 0.04, 0.35, dur - 0.042)
    out = [0.0] * n
    p1 = 0.0
    p2 = 0.0
    for i in range(n):
        t = i / n
        f1 = 220 - 80 * t
        f2 = 233 - 80 * t
        p1 += 2 * math.pi * f1 / SR
        p2 += 2 * math.pi * f2 / SR
        s1 = 1.0 if math.sin(p1) > 0 else -1.0
        s2 = 1.0 if math.sin(p2) > 0 else -1.0
        out[i] = (0.45 * s1 + 0.45 * s2) * env[i] * 0.60
    return _to_pcm(out)


def _gen_chime(freqs: list[float], dur: float = 0.32,
               attack: float = 0.003,
               weights: list[float] | None = None) -> bytes:
    n = int(SR * dur)
    env = _adsr(n, attack, 0.05, 0.55, dur - attack - 0.052)
    if weights is None:
        weights = [1.0] * len(freqs)
    out = [0.0] * n
    phases = [0.0] * len(freqs)
    norm = 1.0 / max(1.0, sum(weights))
    for i in range(n):
        s = 0.0
        for k, f in enumerate(freqs):
            phases[k] += 2 * math.pi * f / SR
            s += weights[k] * math.sin(phases[k])
        out[i] = s * norm * env[i] * 0.60
    return _to_pcm(out)


def _gen_glyph_pickup() -> bytes:
    return _gen_chime([660, 880, 1320, 1760],
                      dur=0.36, attack=0.002,
                      weights=[1.0, 0.85, 0.55, 0.35])


def _gen_heart_pickup() -> bytes:
    return _gen_chime([440, 554, 660], dur=0.40,
                      attack=0.004, weights=[1.0, 0.7, 0.5])


def _gen_stomp() -> bytes:
    """Sharp thud + small upward chirp to sell the bounce-refund."""
    dur = 0.18
    n = int(SR * dur)
    rng = random.Random(31)
    env = _adsr(n, 0.001, 0.04, 0.25, dur - 0.041)
    noise = _noise(rng, n, lp=0.5)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        if t < 0.45:
            f = 120 - 40 * (t / 0.45)
        else:
            f = 180 + 280 * ((t - 0.45) / 0.55)
        phase += 2 * math.pi * f / SR
        out[i] = (0.65 * math.sin(phase) + 0.30 * noise[i]) * env[i] * 0.65
    return _to_pcm(out)


def _gen_catapult() -> bytes:
    """Steam-vent / catapult upward whoosh."""
    dur = 0.32
    n = int(SR * dur)
    rng = random.Random(37)
    env = _adsr(n, 0.005, 0.06, 0.7, dur - 0.066)
    noise = _noise(rng, n, lp=0.65)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 200 + 480 * t
        phase += 2 * math.pi * f / SR
        out[i] = (0.55 * noise[i] + 0.30 * math.sin(phase)) * env[i] * 0.60
    return _to_pcm(out)


def _gen_death() -> bytes:
    """Player death sting — descending tone with rumble."""
    dur = 0.85
    n = int(SR * dur)
    rng = random.Random(41)
    env = _adsr(n, 0.01, 0.20, 0.6, dur - 0.21)
    noise = _noise(rng, n, lp=0.85)
    out = [0.0] * n
    phase = 0.0
    rumble = 0.0
    for i in range(n):
        t = i / n
        f = 330 - 220 * t
        phase += 2 * math.pi * f / SR
        rumble += 2 * math.pi * 50 / SR
        out[i] = (0.55 * math.sin(phase)
                  + 0.30 * math.sin(rumble)
                  + 0.20 * noise[i]) * env[i] * 0.65
    return _to_pcm(out)


def _gen_record() -> bytes:
    return _gen_chime([523, 659, 784, 1046], dur=0.70,
                      attack=0.005, weights=[1.0, 0.9, 0.85, 0.55])


def _gen_title() -> bytes:
    return _gen_chime([440, 660, 880], dur=0.55,
                      attack=0.004, weights=[1.0, 0.7, 0.55])


# ---------------------------------------------------------------------------
# Bank
# ---------------------------------------------------------------------------
class SfxBank:
    """All synthesized sounds + a defensive `play()` API."""

    _SPECS = {
        "jump":         (lambda: _gen_jump(False), 0.55),
        "double_jump":  (lambda: _gen_jump(True),  0.55),
        "wall_jump":    (_gen_wall_jump,           0.65),
        "dash":         (_gen_dash,                0.70),
        "slide":        (_gen_slide,               0.45),
        "land_soft":    (lambda: _gen_land(False), 0.50),
        "land_hard":    (lambda: _gen_land(True),  0.85),
        "bomb_throw":   (_gen_bomb_throw,          0.55),
        "explode":      (_gen_explode,             0.95),
        "hit":          (_gen_hit,                 0.80),
        "glyph_pickup": (_gen_glyph_pickup,        0.65),
        "heart_pickup": (_gen_heart_pickup,        0.75),
        "stomp":        (_gen_stomp,               0.80),
        "catapult":     (_gen_catapult,            0.70),
        "death":        (_gen_death,               0.85),
        "record":       (_gen_record,              0.85),
        "title":        (_gen_title,               0.60),
    }

    def __init__(self) -> None:
        self.enabled = False
        self.master = 0.55
        self._sounds: dict[str, tuple[pygame.mixer.Sound, float]] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 1, 512)
            pygame.mixer.set_num_channels(24)
            for name, (fn, vol) in self._SPECS.items():
                self._sounds[name] = (pygame.mixer.Sound(buffer=fn()), vol)
            self.enabled = True
        except (pygame.error, OSError):
            self.enabled = False

    def play(self, name: str, vol: float = 1.0) -> None:
        if not self.enabled:
            return
        item = self._sounds.get(name)
        if item is None:
            return
        snd, default_vol = item
        snd.set_volume(min(1.0, max(0.0, self.master * default_vol * vol)))
        snd.play()

    def set_master(self, vol: float) -> None:
        self.master = min(1.0, max(0.0, vol))


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------
_INSTANCE: Optional[SfxBank] = None


def init() -> SfxBank:
    """Build (or rebuild) the global sound bank. Safe to call multiple times."""
    global _INSTANCE
    _INSTANCE = SfxBank()
    return _INSTANCE


def get() -> SfxBank:
    """Lazy accessor — builds the bank on first use if init() wasn't called."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SfxBank()
    return _INSTANCE
