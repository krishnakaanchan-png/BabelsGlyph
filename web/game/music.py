"""Procedural ambient music for Babel's Glyph.

Theme: 'ancient tech' — a soothing modal pad over a deep stone-temple
drone, with sparse crystalline glyph bells. Synthesized at startup
using only the standard library (math, array, random) so the bundle
stays small and the web (pygbag) build needs no asset files.

Public API:
    music.init()           # call once after pygame is imported
    music.get().play()     # start looping with fade-in
    music.get().stop()     # fade-out
    music.get().set_volume(0.0..1.0)

If pygame.mixer cannot be initialized, the player becomes a silent
no-op and the game still runs.
"""
from __future__ import annotations

import array
import math
import random
from typing import Optional

import pygame


SR = 22050
LOOP_SEC = 24.0
N_TOTAL = int(LOOP_SEC * SR)

# Integer-phase sine lookup table for fast synthesis without per-sample math.sin().
_LUT_SZ = 4096                       # power of two
_LUT_BITS = 12                       # log2(_LUT_SZ)
_LUT_MASK = _LUT_SZ - 1
_PHASE_BITS = 24
_PHASE_MASK = (1 << _PHASE_BITS) - 1
_SHIFT = _PHASE_BITS - _LUT_BITS
_LUT_AMP = 16384                     # int amplitude of LUT (~Q14)

# Build LUT once.
_LUT = array.array(
    "i", [int(math.sin(2.0 * math.pi * i / _LUT_SZ) * _LUT_AMP) for i in range(_LUT_SZ)]
)


def _add_sine(buf: array.array, freq: float, amp: int, n_start: int, n_dur: int,
              n_attack: int = 0, n_release: int = 0, vib_freq: float = 0.0,
              vib_depth: int = 0, phase0: int = 0) -> None:
    """Mix a sine into ``buf`` with a linear A/R envelope and optional vibrato.

    All envelopes are linear; for soothing pads this sounds smoother than exp.
    """
    if n_dur <= 0:
        return
    inc = int(freq * (1 << _PHASE_BITS) / SR) & _PHASE_MASK
    vinc = int(vib_freq * (1 << _PHASE_BITS) / SR) & _PHASE_MASK
    p = phase0 & _PHASE_MASK
    vp = 0
    LUT = _LUT
    LM = _LUT_MASK
    SH = _SHIFT
    PM = _PHASE_MASK
    n_total = len(buf)
    sustain_start = n_attack
    sustain_end = n_dur - n_release
    # Loop is hot — keep math lean.
    if vib_depth == 0 and vinc == 0:
        for i in range(n_dur):
            if i < sustain_start:
                env_num = i
                env_den = sustain_start if sustain_start > 0 else 1
            elif i >= sustain_end:
                env_num = max(0, n_dur - i)
                env_den = n_release if n_release > 0 else 1
            else:
                env_num = 1
                env_den = 1
            s = LUT[(p >> SH) & LM]
            buf[(n_start + i) % n_total] += (s * amp * env_num) // (env_den * _LUT_AMP)
            p = (p + inc) & PM
    else:
        for i in range(n_dur):
            if i < sustain_start:
                env_num = i
                env_den = sustain_start if sustain_start > 0 else 1
            elif i >= sustain_end:
                env_num = max(0, n_dur - i)
                env_den = n_release if n_release > 0 else 1
            else:
                env_num = 1
                env_den = 1
            vib = (LUT[(vp >> SH) & LM] * vib_depth) >> 14
            s = LUT[((p >> SH) + vib) & LM]
            buf[(n_start + i) % n_total] += (s * amp * env_num) // (env_den * _LUT_AMP)
            p = (p + inc) & PM
            vp = (vp + vinc) & PM


def _add_pluck(buf: array.array, freq: float, amp: int, n_start: int,
               decay_sec: float = 2.5,
               harmonics=(1.0, 0.5, 0.28, 0.14)) -> None:
    """Glyph-bell: damped sum of mildly inharmonic partials with exp decay."""
    n_dur = int(decay_sec * SR)
    if n_dur <= 0:
        return
    n_total = len(buf)
    LUT = _LUT
    LM = _LUT_MASK
    SH = _SHIFT
    PM = _PHASE_MASK
    # Per-harmonic phase increment (slight inharmonic stretch for bell character).
    incs = []
    weights = []
    phases = []
    for h, w in enumerate(harmonics, start=1):
        ratio = h * (1.0 + 0.0009 * (h - 1) ** 2)
        incs.append(int(freq * ratio * (1 << _PHASE_BITS) / SR) & PM)
        weights.append(int(w * 1024))
        phases.append(0)
    # exp decay table to avoid per-sample math.exp.
    DEC_TBL_SZ = 512
    decay_tbl = array.array(
        "i",
        [int(math.exp(-5.5 * i / DEC_TBL_SZ) * 1024) for i in range(DEC_TBL_SZ)],
    )
    step = max(1, n_dur // DEC_TBL_SZ)
    for i in range(n_dur):
        env = decay_tbl[min(DEC_TBL_SZ - 1, i // step)]
        s = 0
        for j in range(len(incs)):
            s += LUT[(phases[j] >> SH) & LM] * weights[j]
            phases[j] = (phases[j] + incs[j]) & PM
        # s currently scaled by _LUT_AMP*1024.
        buf[(n_start + i) % n_total] += (s * amp * env) >> 34


def _add_noise(buf: array.array, amp: int, n_start: int, n_dur: int,
               lp_alpha: float = 0.04, mod_freq: float = 0.07) -> None:
    """Soft filtered-noise wash with slow amplitude breathing."""
    n_total = len(buf)
    LUT = _LUT
    LM = _LUT_MASK
    SH = _SHIFT
    PM = _PHASE_MASK
    rng = random.Random(7)
    # state in Q14
    state = 0
    a = max(1, int(lp_alpha * 16384))
    minc = int(mod_freq * (1 << _PHASE_BITS) / SR) & PM
    mp = 0
    for i in range(n_dur):
        x = rng.randint(-_LUT_AMP, _LUT_AMP)
        state += (a * (x - state)) >> 14
        # breathing: 0.5 + 0.5*sin → 0..1 in Q14 (0..16384)
        m = 8192 + (LUT[(mp >> SH) & LM] >> 1)  # 0..16384
        buf[(n_start + i) % n_total] += (state * amp * m) >> 28
        mp = (mp + minc) & PM


def _render_track() -> bytes:
    """Render the full looping ambient track to mono int16 PCM bytes."""
    # Accumulator buffer in int32 (to avoid clipping during sum).
    buf = array.array("i", [0] * N_TOTAL)

    # ---- Layer 1: Deep stone-temple drone (perfect-fifth pedal) -------
    # Low A (110 Hz) + E (165 Hz) + sub-A (55 Hz). Slow sub-Hz vibrato so
    # the drone breathes without ever feeling pitched.
    _add_sine(buf, 110.0, 4500, 0, N_TOTAL,
              vib_freq=0.13, vib_depth=14)
    _add_sine(buf, 165.0, 2800, 0, N_TOTAL,
              vib_freq=0.09, vib_depth=10)
    _add_sine(buf, 55.0, 2400, 0, N_TOTAL)

    # ---- Layer 2: Modal chord pad — 4 chords × 6 sec each --------------
    # A natural-minor extensions: i7  →  VImaj7  →  IIImaj7  →  v7
    # The drop from C-major-ish brightness back to Em gives that bittersweet
    # 'ruined civilization' feel that matches the ancient-tech motif.
    chord_dur_s = LOOP_SEC / 4
    chord_n = int(chord_dur_s * SR)
    chords = [
        # Am7   : A   C       E      G
        [220.00, 261.63, 329.63, 392.00],
        # Fmaj7 : F   A       C      E
        [174.61, 220.00, 261.63, 329.63],
        # Cmaj7 : C   E       G      B
        [261.63, 329.63, 392.00, 493.88],
        # Em7   : E   G       B      D
        [164.81, 196.00, 246.94, 293.66],
    ]
    n_attack = int(2.0 * SR)
    n_release = int(2.0 * SR)
    for ci, notes in enumerate(chords):
        n0 = ci * chord_n
        for ni, freq in enumerate(notes):
            voice_amp = int(1300 * (1.0 - 0.10 * ni))   # root loudest
            _add_sine(buf, freq, voice_amp, n0, chord_n,
                      n_attack=n_attack, n_release=n_release,
                      vib_freq=0.21 + ni * 0.04, vib_depth=2)
            # Slight detune for a natural chorus shimmer.
            _add_sine(buf, freq * 1.0035, int(voice_amp * 0.55), n0, chord_n,
                      n_attack=n_attack, n_release=n_release)

    # ---- Layer 3: Sparse glyph bells ----------------------------------
    # Minor-pentatonic above the pad, plus one octave for sparkle.
    pent = [
        220.00, 261.63, 293.66, 329.63, 392.00,
        440.00, 523.25, 587.33, 659.25,
    ]
    rng = random.Random(42)
    t = 1.5
    while t < LOOP_SEC - 3.5:
        freq = rng.choice(pent)
        n_start = int(t * SR)
        amp = rng.randint(2400, 3600)
        _add_pluck(buf, freq, amp, n_start, decay_sec=2.6)
        t += rng.uniform(2.7, 5.0)

    # ---- Layer 4: Wind through ruins ---------------------------------
    _add_noise(buf, 1100, 0, N_TOTAL, lp_alpha=0.04, mod_freq=0.07)

    # ---- Master: soft tanh + int16 conversion ------------------------
    out = array.array("h", [0] * N_TOTAL)
    # Find peak first, then pre-scale so the loudest sample sits at ~0.85.
    peak = 1
    for v in buf:
        av = v if v >= 0 else -v
        if av > peak:
            peak = av
    target = int(0.78 * 32767)
    pre = target / peak if peak > 0 else 1.0
    drive = 0.95
    for i in range(N_TOTAL):
        x = buf[i] * pre / 32768.0
        # tanh soft-clip preserves headroom on the rare spike.
        y = math.tanh(x * drive)
        v = int(y * 32767)
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        out[i] = v
    return out.tobytes()


# ---------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------

class MusicPlayer:
    """Loops the synthesized ambient track on a reserved mixer channel."""

    def __init__(self) -> None:
        self.enabled = False
        self.muted = False
        self._channel: Optional["pygame.mixer.Channel"] = None
        self._sound: Optional["pygame.mixer.Sound"] = None
        self._volume = 0.45

    def init(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 1, 512)
        except pygame.error:
            self.enabled = False
            return
        try:
            if pygame.mixer.get_num_channels() < 32:
                pygame.mixer.set_num_channels(32)
            # Reserve channel 0 for music so SFX (Sound.play auto-pick) skip it.
            pygame.mixer.set_reserved(1)
            self._channel = pygame.mixer.Channel(0)
        except Exception:
            self.enabled = False
            return
        try:
            data = _render_track()
            self._sound = pygame.mixer.Sound(buffer=data)
            self.enabled = True
        except Exception:
            self.enabled = False

    def play(self, fade_ms: int = 2000) -> None:
        if not self.enabled or self.muted:
            return
        if self._sound is None or self._channel is None:
            return
        if self._channel.get_busy():
            return
        self._channel.set_volume(self._volume)
        self._channel.play(self._sound, loops=-1, fade_ms=fade_ms)

    def stop(self, fade_ms: int = 1500) -> None:
        if not self.enabled or self._channel is None:
            return
        self._channel.fadeout(fade_ms)

    def set_volume(self, v: float) -> None:
        self._volume = max(0.0, min(1.0, v))
        if self._channel is not None:
            try:
                self._channel.set_volume(self._volume)
            except Exception:
                pass

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)
        if not self.enabled or self._channel is None:
            return
        if self.muted:
            # Soft fade so the toggle itself never clicks.
            try:
                self._channel.fadeout(220)
            except Exception:
                pass
        else:
            # Resume from start of loop with a gentle fade-in.
            self.play(fade_ms=600)

    def toggle_muted(self) -> bool:
        self.set_muted(not self.muted)
        return self.muted


_INSTANCE: Optional[MusicPlayer] = None


def init() -> MusicPlayer:
    """Create and initialise the singleton music player."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = MusicPlayer()
        _INSTANCE.init()
    return _INSTANCE


def get() -> MusicPlayer:
    return _INSTANCE if _INSTANCE is not None else init()
