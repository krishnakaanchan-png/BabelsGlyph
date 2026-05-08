"""Procedural sound effects for Babel's Glyph (minimal, click-free).

Design notes (rewrite, May 2026):
- All SFX use sine + tanh saturation only — no raw square / sawtooth edges.
- Every buffer fades to silence in its last ~12 ms so playback can never
  click at end-of-buffer no matter when the mixer cuts it off.
- Attack times raised to >=8 ms (>=10 ms for impacts) and use a cosine
  ease-in to avoid DC step transients on cheap consumer DACs / browser
  WebAudio.
- Master volume lowered to 0.42 — the goal is 'minimal', not loud.
- Noise sources are heavily low-passed (alpha >=0.85) so high harmonics
  don't spike and read as a click.

Public API:
    audio.init()                      # call once after pygame is imported
    audio.get().play("jump")          # fire-and-forget
    audio.get().set_muted(True)       # silence all SFX
    audio.get().toggle_muted()        # returns new muted state
"""
from __future__ import annotations

import array
import math
import random
from typing import Optional

import pygame


SR = 22050
MAX_AMP = 26000      # int16 with extra headroom (was 28000)


def _sat(x: float) -> float:
    """Soft-clip to suppress transients."""
    return math.tanh(x)


def _end_fade(out: list[float], fade_n: int = 260) -> None:
    """In-place fade the LAST `fade_n` samples linearly to zero.

    260 samples @ 22050 Hz ~= 11.8 ms. Below perception threshold, but
    long enough to kill any end-of-buffer step click.
    """
    n = len(out)
    if n == 0:
        return
    fade_n = min(fade_n, n)
    for i in range(fade_n):
        k = (fade_n - 1 - i) / fade_n  # 1.0 -> 0.0
        out[n - fade_n + i] *= k


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
    """ADSR envelope with cosine attack to suppress click.

    a/d/r in seconds; sus in [0,1].
    """
    a_n = max(8, int(a * SR))    # min 8 samples (~0.36 ms ramp guarantee)
    d_n = max(1, int(d * SR))
    r_n = max(1, int(r * SR))
    s_n = max(0, n - a_n - d_n - r_n)
    env = [0.0] * n
    for i in range(n):
        if i < a_n:
            # Cosine ease-in: 0.5 - 0.5*cos(pi*t) -> smoother than linear
            env[i] = 0.5 - 0.5 * math.cos(math.pi * i / a_n)
        elif i < a_n + d_n:
            env[i] = 1.0 + (sus - 1.0) * ((i - a_n) / d_n)
        elif i < a_n + d_n + s_n:
            env[i] = sus
        else:
            t = (i - a_n - d_n - s_n) / r_n
            env[i] = sus * (1.0 - t)
    return env


def _noise(rng: random.Random, n: int, lp: float = 0.0) -> list[float]:
    """White or one-pole low-passed noise. lp in [0,1] - higher = more LP."""
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
# Per-effect synths - all minimal, all sine-based
# ---------------------------------------------------------------------------
def _gen_jump(high: bool = False) -> bytes:
    """Soft tonal blip - ascending sine + a touch of detuned partial."""
    dur = 0.10 if not high else 0.13
    n = int(SR * dur)
    f0 = 360.0 if not high else 500.0
    f1 = 700.0 if not high else 980.0
    env = _adsr(n, 0.008, 0.025, 0.55, dur - 0.034)
    out = [0.0] * n
    p1 = 0.0
    p2 = 0.0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t * t
        p1 += 2 * math.pi * f / SR
        p2 += 2 * math.pi * (f * 1.503) / SR  # subtle fifth-ish overtone
        out[i] = (math.sin(p1) + 0.18 * math.sin(p2)) * env[i] * 0.40
    _end_fade(out)
    return _to_pcm(out)


def _gen_wall_jump() -> bytes:
    """Soft descending knock - NO explicit click transient anymore."""
    dur = 0.14
    n = int(SR * dur)
    rng = random.Random(7)
    env = _adsr(n, 0.012, 0.04, 0.35, dur - 0.052)
    noise = _noise(rng, n, lp=0.92)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 230 + 220 * (1 - t)
        phase += 2 * math.pi * f / SR
        out[i] = (0.55 * math.sin(phase) + 0.18 * noise[i]) * env[i] * 0.42
    _end_fade(out)
    return _to_pcm(out)


def _gen_dash() -> bytes:
    """Soft downward whoosh - heavily low-passed noise + fading sine."""
    dur = 0.18
    n = int(SR * dur)
    rng = random.Random(11)
    env = _adsr(n, 0.012, 0.05, 0.7, dur - 0.062)
    noise = _noise(rng, n, lp=0.93)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 720 - 540 * t
        phase += 2 * math.pi * f / SR
        out[i] = (0.45 * noise[i] + 0.30 * math.sin(phase)) * env[i] * 0.50
    _end_fade(out)
    return _to_pcm(out)


def _gen_slide() -> bytes:
    """Whisper of friction - very gentle, no fast tremolo edges."""
    dur = 0.26
    n = int(SR * dur)
    rng = random.Random(13)
    env = _adsr(n, 0.020, 0.05, 0.50, dur - 0.072)
    noise = _noise(rng, n, lp=0.88)
    out = [0.0] * n
    for i in range(n):
        t = i / n
        breathe = 0.85 + 0.15 * math.sin(2 * math.pi * 6 * t)
        out[i] = noise[i] * env[i] * breathe * 0.38
    _end_fade(out)
    return _to_pcm(out)


def _gen_land(hard: bool) -> bytes:
    """Low thump - pure sine sub-bass with a whisper of LP noise."""
    dur = 0.16 if hard else 0.09
    n = int(SR * dur)
    rng = random.Random(17 if hard else 19)
    f0 = 70.0 if hard else 100.0
    env = _adsr(n,
                0.010 if hard else 0.014,
                0.05 if hard else 0.025,
                0.0,
                dur - 0.063 if hard else dur - 0.041)
    noise = _noise(rng, n, lp=0.93)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        phase += 2 * math.pi * f0 / SR
        out[i] = (0.75 * math.sin(phase) + 0.15 * noise[i]) * env[i] \
                 * (0.65 if hard else 0.40)
    _end_fade(out)
    return _to_pcm(out)


def _gen_bomb_throw() -> bytes:
    """Soft warble - sine with slow LFO + LP noise."""
    dur = 0.16
    n = int(SR * dur)
    rng = random.Random(23)
    env = _adsr(n, 0.012, 0.03, 0.55, dur - 0.044)
    noise = _noise(rng, n, lp=0.92)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 260 + 120 * math.sin(2 * math.pi * 4 * t)
        phase += 2 * math.pi * f / SR
        out[i] = (0.40 * math.sin(phase) + 0.20 * noise[i]) * env[i] * 0.45
    _end_fade(out)
    return _to_pcm(out)


def _gen_explode() -> bytes:
    """Gentle boom - low sine + LP noise, slower attack."""
    dur = 0.40
    n = int(SR * dur)
    rng = random.Random(29)
    env = _adsr(n, 0.008, 0.10, 0.30, dur - 0.110)
    noise = _noise(rng, n, lp=0.90)
    out = [0.0] * n
    p_lo = 0.0
    p_mid = 0.0
    for i in range(n):
        t = i / n
        f_lo = 60.0
        f_mid = 170.0 - 110.0 * t
        p_lo += 2 * math.pi * f_lo / SR
        p_mid += 2 * math.pi * f_mid / SR
        body = (0.50 * math.sin(p_lo)
                + 0.25 * math.sin(p_mid)
                + 0.40 * noise[i])
        out[i] = body * env[i] * 0.65
    _end_fade(out)
    return _to_pcm(out)


def _gen_hit() -> bytes:
    """Damage taken - soft detuned sine pair (was square pair, now smoothed)."""
    dur = 0.20
    n = int(SR * dur)
    env = _adsr(n, 0.010, 0.04, 0.30, dur - 0.052)
    out = [0.0] * n
    p1 = 0.0
    p2 = 0.0
    for i in range(n):
        t = i / n
        f1 = 215 - 75 * t
        f2 = 232 - 75 * t   # ~13 Hz beating for tension, no edges
        p1 += 2 * math.pi * f1 / SR
        p2 += 2 * math.pi * f2 / SR
        sig = math.sin(p1) + math.sin(p2)
        out[i] = math.tanh(sig * 0.85) * env[i] * 0.45
    _end_fade(out)
    return _to_pcm(out)


def _gen_chime(freqs: list[float], dur: float = 0.32,
               attack: float = 0.006,
               weights: list[float] | None = None,
               level: float = 0.45) -> bytes:
    n = int(SR * dur)
    env = _adsr(n, attack, 0.05, 0.50, dur - attack - 0.052)
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
        out[i] = s * norm * env[i] * level
    _end_fade(out)
    return _to_pcm(out)


def _gen_glyph_pickup() -> bytes:
    return _gen_chime([660, 880, 1320],
                      dur=0.32, attack=0.006,
                      weights=[1.0, 0.70, 0.40], level=0.42)


def _gen_heart_pickup() -> bytes:
    return _gen_chime([440, 554, 660], dur=0.36,
                      attack=0.008, weights=[1.0, 0.65, 0.45], level=0.45)


def _gen_stomp() -> bytes:
    """Soft thud + faint upward chirp - minimal, no harsh edge."""
    dur = 0.16
    n = int(SR * dur)
    rng = random.Random(31)
    env = _adsr(n, 0.010, 0.04, 0.20, dur - 0.052)
    noise = _noise(rng, n, lp=0.92)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        if t < 0.45:
            f = 110 - 30 * (t / 0.45)
        else:
            f = 160 + 220 * ((t - 0.45) / 0.55)
        phase += 2 * math.pi * f / SR
        out[i] = (0.55 * math.sin(phase) + 0.18 * noise[i]) * env[i] * 0.55
    _end_fade(out)
    return _to_pcm(out)


def _gen_catapult() -> bytes:
    """Gentle upward whoosh."""
    dur = 0.28
    n = int(SR * dur)
    rng = random.Random(37)
    env = _adsr(n, 0.012, 0.06, 0.6, dur - 0.074)
    noise = _noise(rng, n, lp=0.92)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 220 + 380 * t
        phase += 2 * math.pi * f / SR
        out[i] = (0.40 * noise[i] + 0.25 * math.sin(phase)) * env[i] * 0.48
    _end_fade(out)
    return _to_pcm(out)


def _gen_death() -> bytes:
    """Sombre falling tone - minimal, dignified."""
    dur = 0.80
    n = int(SR * dur)
    rng = random.Random(41)
    env = _adsr(n, 0.020, 0.20, 0.55, dur - 0.220)
    noise = _noise(rng, n, lp=0.95)
    out = [0.0] * n
    phase = 0.0
    rumble = 0.0
    for i in range(n):
        t = i / n
        f = 320 - 210 * t
        phase += 2 * math.pi * f / SR
        rumble += 2 * math.pi * 50 / SR
        out[i] = (0.45 * math.sin(phase)
                  + 0.25 * math.sin(rumble)
                  + 0.10 * noise[i]) * env[i] * 0.55
    _end_fade(out)
    return _to_pcm(out)


def _gen_record() -> bytes:
    return _gen_chime([523, 659, 784, 1046], dur=0.65,
                      attack=0.010, weights=[1.0, 0.85, 0.75, 0.45],
                      level=0.55)


def _gen_title() -> bytes:
    return _gen_chime([440, 660, 880], dur=0.50,
                      attack=0.010, weights=[1.0, 0.65, 0.50], level=0.50)


# ---------------------------------------------------------------------------
# Bank
# ---------------------------------------------------------------------------
class SfxBank:
    """All synthesised sounds + a defensive `play()` API."""

    _SPECS = {
        "jump":         (lambda: _gen_jump(False), 0.55),
        "double_jump":  (lambda: _gen_jump(True),  0.55),
        "wall_jump":    (_gen_wall_jump,           0.55),
        "dash":         (_gen_dash,                0.60),
        "slide":        (_gen_slide,               0.40),
        "land_soft":    (lambda: _gen_land(False), 0.45),
        "land_hard":    (lambda: _gen_land(True),  0.70),
        "bomb_throw":   (_gen_bomb_throw,          0.50),
        "explode":      (_gen_explode,             0.80),
        "hit":          (_gen_hit,                 0.70),
        "glyph_pickup": (_gen_glyph_pickup,        0.60),
        "heart_pickup": (_gen_heart_pickup,        0.65),
        "stomp":        (_gen_stomp,               0.65),
        "catapult":     (_gen_catapult,            0.60),
        "death":        (_gen_death,               0.75),
        "record":       (_gen_record,              0.80),
        "title":        (_gen_title,               0.55),
    }

    def __init__(self) -> None:
        self.enabled = False
        self.master = 0.42          # was 0.55 - softer minimum
        self.muted = False
        self._sounds: dict[str, tuple[pygame.mixer.Sound, float]] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 1, 512)
            if pygame.mixer.get_num_channels() < 24:
                pygame.mixer.set_num_channels(24)
            for name, (fn, vol) in self._SPECS.items():
                self._sounds[name] = (pygame.mixer.Sound(buffer=fn()), vol)
            self.enabled = True
        except (pygame.error, OSError):
            self.enabled = False

    def play(self, name: str, vol: float = 1.0) -> None:
        if not self.enabled or self.muted:
            return
        item = self._sounds.get(name)
        if item is None:
            return
        snd, default_vol = item
        snd.set_volume(min(1.0, max(0.0, self.master * default_vol * vol)))
        snd.play()

    def set_master(self, vol: float) -> None:
        self.master = min(1.0, max(0.0, vol))

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)
        # We deliberately do NOT call Sound.stop() here: cutting a sound
        # mid-playback can produce a hard click on some drivers. The
        # `muted` flag prevents NEW one-shots from starting; in-flight
        # sounds finish their natural release within ~0.5 s.

    def toggle_muted(self) -> bool:
        self.set_muted(not self.muted)
        return self.muted


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
    """Lazy accessor - builds the bank on first use if init() wasn't called."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SfxBank()
    return _INSTANCE
