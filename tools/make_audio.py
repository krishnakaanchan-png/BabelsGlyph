"""Trailer audio: cinematic synth score + Azure Neural TTS narration.

Generates a 30-second mono WAV at 44.1 kHz that lines up with the timeline in
`make_promo.py`.

Narration:
  * **Primary:** Azure Cognitive Services Speech (neural voice + SSML for
    theatrical prosody, pauses, and emphasis). Voice / key / region come
    from environment variables, falling back to a `.env` file at the
    workspace root, then to `Microsoft David Desktop` via Windows SAPI.
  * **Fallback:** Windows SAPI 5 if Azure is unavailable, so the script
    still produces audio on any Windows machine.

Music:
  * Numpy-only synth: sub-bass drone, evolving pad chords, kick + snare,
    riser, lead motifs, final logo-slam crash + boom.
  * Sidechain ducking under each spoken line.

Standalone usage:
    python tools/make_audio.py
"""
from __future__ import annotations

import math
import os
import random
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
DURATION_S = 30.0
SR = 44100
DEFAULT_OUT = ROOT / "BabelsGlyph_Promo_audio.wav"


# ---------------------------------------------------------------------------
# Narration timeline.
#
# Each entry is `(start_time_s, ssml_body, plain_text_for_sapi, gain)`.
# The ssml_body is the inner contents that go inside <voice>...</voice> in
# the SSML envelope; <prosody>, <break>, <emphasis>, <p>, <s> are all fair
# game. Plain text is used for the SAPI fallback only.
#
# Lines are written longer + more theatrical than v1 — short, punchy
# sentences with deliberate pauses so the narrator can _act_.
# ---------------------------------------------------------------------------
NARRATION: list[tuple[float, str, str, float]] = [
    (
        0.30,
        # Cold-open: hushed but tight enough to land before the slam at 5.0s.
        '<prosody rate="-6%" pitch="-3st">'
        'One forgotten <emphasis level="moderate">library</emphasis>'
        '<break time="220ms"/> '
        'held every secret <emphasis level="strong">of the past.</emphasis>'
        '</prosody>',
        "One forgotten library held every secret of the past.",
        1.00,
    ),
    (
        5.20,
        # Punchy follow-up to the logo slam.
        '<prosody rate="+0%" pitch="-1st">'
        'And now<break time="180ms"/> '
        '<emphasis level="strong">the past is awake.</emphasis>'
        '</prosody>',
        "And now... the past is awake.",
        1.00,
    ),
    (
        7.80,
        # Movement beat: clipped, kinetic.
        '<prosody rate="+2%" pitch="-1st">'
        'Leap<break time="110ms"/> dash<break time="110ms"/> '
        '<emphasis level="strong">wall-run.</emphasis>'
        '</prosody>',
        "Leap. Dash. Wall-run.",
        1.00,
    ),
    (
        10.30,
        # Combat beat.
        '<prosody rate="+4%" pitch="-1st">'
        'Hurl glyphs<break time="120ms"/> '
        'crush <emphasis level="strong">sentinels.</emphasis>'
        '</prosody>',
        "Hurl glyphs. Crush sentinels.",
        1.00,
    ),
    (
        12.85,
        # Zone tour line 1.
        '<prosody rate="-2%" pitch="-2st">'
        'Through <emphasis level="moderate">sandstone ruins</emphasis>'
        '<break time="160ms"/>'
        '</prosody>',
        "Through sandstone ruins...",
        0.95,
    ),
    (
        15.40,
        '<prosody rate="-2%" pitch="-2st">'
        'into da Vinci\u2019s '
        '<emphasis level="moderate">burning forge</emphasis>'
        '<break time="160ms"/>'
        '</prosody>',
        "...into da Vinci's burning forge...",
        0.95,
    ),
    (
        17.95,
        '<prosody rate="+0%" pitch="-1st">'
        'and the workshop '
        '<emphasis level="strong">above the clouds.</emphasis>'
        '</prosody>',
        "...and the workshop above the clouds.",
        0.95,
    ),
    (
        20.20,
        # Threat block.
        '<prosody rate="+8%" pitch="-1st">'
        '<emphasis level="strong">Spikes.</emphasis><break time="100ms"/> '
        '<emphasis level="strong">Steam.</emphasis><break time="100ms"/> '
        '<emphasis level="strong">Steel.</emphasis>'
        '</prosody>',
        "Spikes. Steam. Steel.",
        1.05,
    ),
    (
        23.15,
        '<prosody rate="+0%" pitch="-1st">'
        'Outrun history<break time="180ms"/> '
        '<emphasis level="strong">write your legend.</emphasis>'
        '</prosody>',
        "Outrun history. Write your legend.",
        1.05,
    ),
    (
        25.55,
        # Logo slam: slow, weighty.
        '<prosody rate="-22%" pitch="-3st">'
        '<emphasis level="strong">Babel\u2019s Glyph.</emphasis>'
        '</prosody>',
        "Babel's Glyph.",
        1.10,
    ),
    (
        28.30,
        '<prosody rate="-4%" pitch="-1st">'
        '<emphasis level="strong">Out now.</emphasis>'
        '</prosody>',
        "Out now.",
        1.05,
    ),
]


# ---------------------------------------------------------------------------
# Oscillator / envelope helpers
# ---------------------------------------------------------------------------
def _t(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / SR


def sine(f: float, t: np.ndarray) -> np.ndarray:
    return np.sin(2 * np.pi * f * t)


def saw(f: float, t: np.ndarray, harmonics: int = 10) -> np.ndarray:
    out = np.zeros_like(t)
    for k in range(1, harmonics + 1):
        out += np.sin(2 * np.pi * f * k * t) / k
    return out * (2.0 / np.pi)


def triangle(f: float, t: np.ndarray, harmonics: int = 8) -> np.ndarray:
    out = np.zeros_like(t)
    for k in range(harmonics):
        n = 2 * k + 1
        out += ((-1) ** k) * np.sin(2 * np.pi * f * n * t) / (n * n)
    return out * (8.0 / (np.pi * np.pi))


def adsr(n: int, a: float = 0.02, d: float = 0.05,
         s_level: float = 0.7, r: float = 0.1) -> np.ndarray:
    A = max(1, int(a * SR))
    D = max(1, int(d * SR))
    R = max(1, int(r * SR))
    S = max(0, n - A - D - R)
    env = np.concatenate([
        np.linspace(0.0, 1.0, A),
        np.linspace(1.0, s_level, D),
        np.full(S, s_level),
        np.linspace(s_level, 0.0, R),
    ])
    if len(env) < n:
        env = np.concatenate([env, np.zeros(n - len(env))])
    return env[:n].astype(np.float64)


def kick(dur: float = 0.45) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    f = 110.0 * np.exp(-t * 28.0) + 45.0
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase)
    click = np.exp(-t * 220) * np.random.uniform(-1, 1, n) * 0.25
    env = np.exp(-t * 7.0)
    return (body + click) * env


def snare(dur: float = 0.22) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    noise = np.random.uniform(-1, 1, n)
    tone = np.sin(2 * np.pi * 200 * t)
    env = np.exp(-t * 15.0)
    return (noise * 0.7 + tone * 0.3) * env


def crash(dur: float = 2.5) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    noise = np.random.uniform(-1, 1, n)
    noise = np.diff(noise, prepend=0.0)
    env = np.exp(-t * 1.7)
    return noise * env


def riser(dur: float = 1.5) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    noise = np.random.uniform(-1, 1, n)
    env_n = (t / dur) ** 1.6
    sweep_freq = 220 + 1500 * (t / dur) ** 2
    sweep_phase = 2 * np.pi * np.cumsum(sweep_freq) / SR
    tone = np.sin(sweep_phase) * env_n * 0.45
    return noise * env_n * 0.55 + tone


def add_at(dst: np.ndarray, src: np.ndarray, t_start: float, gain: float = 1.0) -> None:
    i = int(t_start * SR)
    if i >= len(dst):
        return
    if i < 0:
        src = src[-i:]
        i = 0
    end = min(len(dst), i + len(src))
    if end > i:
        dst[i:end] += src[: end - i] * gain


def fade_env(t: np.ndarray, start: float, end: float,
             fade_in: float = 0.4, fade_out: float = 0.4) -> np.ndarray:
    fi = np.clip((t - start) / max(1e-6, fade_in), 0.0, 1.0)
    fo = np.clip((end - t) / max(1e-6, fade_out), 0.0, 1.0)
    env = np.minimum(fi, fo)
    return np.clip(env, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------
A_MIN = [110.0, 220.0, 261.63, 329.63]
F_MAJ = [87.31, 174.61, 220.0, 349.23]
G_MAJ = [98.0, 196.0, 246.94, 392.0]
A_TENSE = [110.0, 220.0, 311.13, 369.99]
A_TRIUMPH = [110.0, 220.0, 329.63, 440.0, 659.25]

CHORDS = [
    (0.0, 2.5, A_MIN, 0.04),
    (2.5, 5.0, A_MIN, 0.10),
    (5.0, 7.5, A_MIN, 0.07),
    (7.5, 10.0, F_MAJ, 0.07),
    (10.0, 12.5, G_MAJ, 0.08),
    (12.5, 15.0, A_MIN, 0.09),
    (15.0, 17.5, F_MAJ, 0.09),
    (17.5, 20.0, G_MAJ, 0.10),
    (20.0, 22.5, A_TENSE, 0.10),
    (22.5, 25.0, A_TENSE, 0.11),
    (25.0, 28.0, A_TRIUMPH, 0.10),
    (28.0, 30.0, A_TRIUMPH, 0.06),
]


def synth_music(duration: float = DURATION_S) -> np.ndarray:
    n = int(duration * SR)
    t = _t(n)
    out = np.zeros(n, dtype=np.float64)

    # Sub-bass drone with section-dependent gain.
    bass_env = np.minimum(np.clip(t / 0.8, 0, 1),
                          np.clip((duration - t) / 1.0, 0, 1))
    section_gain = np.ones_like(t) * 0.18
    section_gain[t < 2.5] = 0.06
    section_gain[(t >= 12.5) & (t < 20.0)] = 0.22
    section_gain[(t >= 20.0) & (t < 25.0)] = 0.28
    section_gain[(t >= 25.0) & (t < 28.0)] = 0.30
    section_gain[t >= 28.0] = 0.10
    bass = (sine(55.0, t) + sine(55.6, t) * 0.5) * bass_env * section_gain
    out += bass

    # Pad chords.
    for s, e, freqs, vgain in CHORDS:
        env = fade_env(t, s, e, fade_in=0.35, fade_out=0.4)
        for f in freqs:
            wave = (saw(f, t, harmonics=6) * 0.4
                    + triangle(f, t, harmonics=4) * 0.6)
            out += wave * env * vgain * 0.5

    # First slam.
    add_at(out, kick(0.6), 2.50, gain=0.85)
    add_at(out, crash(2.5), 2.50, gain=0.55)

    # Heartbeat (5-12.5).
    for i in range(8):
        ts = 5.0 + i * 1.0
        if ts >= 12.5:
            break
        add_at(out, kick(0.4), ts, gain=0.45 + 0.04 * i)

    # Groove (12.5-20) at 100 BPM.
    bpm = 100
    beat = 60.0 / bpm
    ts = 12.5
    while ts < 20.0:
        add_at(out, kick(0.35), ts, gain=0.65)
        if ts + beat * 2 < 20.0:
            add_at(out, kick(0.35), ts + beat * 2, gain=0.6)
        if ts + beat < 20.0:
            add_at(out, snare(0.2), ts + beat, gain=0.4)
        if ts + beat * 3 < 20.0:
            add_at(out, snare(0.2), ts + beat * 3, gain=0.4)
        ts += beat * 4

    # Climax (20-25) at 130 BPM.
    bpm = 130
    beat = 60.0 / bpm
    ts = 20.0
    while ts < 25.0:
        add_at(out, kick(0.32), ts, gain=0.75)
        if ts + beat < 25.0:
            add_at(out, snare(0.18), ts + beat, gain=0.5)
        ts += beat * 2
    add_at(out, riser(2.0), 23.0, gain=0.6)

    # Final logo slam.
    add_at(out, kick(0.7), 25.0, gain=1.0)
    add_at(out, crash(3.5), 25.0, gain=0.6)
    n_boom = int(2.0 * SR)
    t_b = _t(n_boom)
    boom = sine(40.0, t_b) * np.exp(-t_b * 1.4) * 0.5
    add_at(out, boom, 25.0, gain=1.0)

    # Lead motif.
    motif = [
        (0.0, 659.25, 0.6),
        (0.6, 783.99, 0.6),
        (1.2, 880.00, 1.2),
        (2.4, 783.99, 0.4),
        (2.8, 659.25, 0.4),
        (3.2, 523.25, 0.6),
        (3.8, 440.00, 1.6),
    ]
    for phrase_start in (12.6, 16.2):
        for off, f, dur in motif:
            ts = phrase_start + off
            if ts >= 20.0:
                break
            ns = int(dur * SR)
            t_local = _t(ns)
            vib = 1.0 + 0.005 * np.sin(2 * np.pi * 5.5 * t_local)
            wave = triangle(f, t_local * vib, harmonics=6) * 0.18
            wave += saw(f * 2.0, t_local, harmonics=4) * 0.03
            env = adsr(ns, a=0.025, d=0.06, s_level=0.75, r=0.18)
            add_at(out, wave * env, ts, gain=1.0)

    # Climax motif.
    climax_motif = [
        (0.00, 880.00, 0.30),
        (0.30, 783.99, 0.30),
        (0.60, 880.00, 0.30),
        (0.90, 1046.50, 0.30),
        (1.20, 880.00, 0.60),
        (1.80, 783.99, 0.30),
        (2.10, 659.25, 0.30),
        (2.40, 880.00, 1.20),
    ]
    for phrase_start in (20.05, 22.55):
        for off, f, dur in climax_motif:
            ts = phrase_start + off
            if ts >= 25.0:
                break
            ns = int(dur * SR)
            t_local = _t(ns)
            wave = saw(f, t_local, harmonics=8) * 0.10
            wave += triangle(f, t_local, harmonics=4) * 0.05
            env = adsr(ns, a=0.012, d=0.04, s_level=0.55, r=0.06)
            add_at(out, wave * env, ts, gain=1.0)

    # Final sustained chord.
    n_final = int(3.0 * SR)
    t_f = _t(n_final)
    chord = np.zeros(n_final)
    for f in (110.0, 220.0, 329.63, 440.0, 659.25):
        chord += saw(f, t_f, harmonics=6) * 0.04
        chord += triangle(f, t_f, harmonics=4) * 0.03
    chord *= adsr(n_final, a=0.02, d=0.6, s_level=0.65, r=0.8)
    add_at(out, chord, 25.0, gain=1.0)

    # Resolve.
    n_res = int(2.0 * SR)
    t_r = _t(n_res)
    res = (triangle(220.0, t_r, harmonics=6) * 0.05
           + triangle(440.0, t_r, harmonics=4) * 0.04)
    res *= adsr(n_res, a=0.05, d=0.3, s_level=0.6, r=1.0)
    add_at(out, res, 28.0, gain=1.0)

    # Logo ping.
    n_p = int(1.6 * SR)
    t_p = _t(n_p)
    ping = (sine(880.0, t_p) * 0.20 + sine(1320.0, t_p) * 0.10)
    ping *= np.exp(-t_p * 1.6)
    add_at(out, ping, 25.05, gain=1.0)

    # Tape hiss floor.
    hiss = np.random.uniform(-1, 1, n) * 0.008
    out += hiss

    return out


# ---------------------------------------------------------------------------
# Credentials helper — reads env vars first, then `.env` at workspace root.
# ---------------------------------------------------------------------------
def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as fp:
            for raw in fp:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # Don't override real env vars.
                os.environ.setdefault(key, val)
    except OSError:
        pass


def _azure_creds() -> tuple[str | None, str | None, str]:
    _load_dotenv()
    key = os.environ.get("AZURE_SPEECH_KEY")
    region = os.environ.get("AZURE_SPEECH_REGION")
    voice = os.environ.get("AZURE_SPEECH_VOICE",
                           "en-US-AndrewMultilingualNeural")
    return key, region, voice


# ---------------------------------------------------------------------------
# WAV I/O helpers
# ---------------------------------------------------------------------------
def _read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nf = w.getnframes()
        raw = w.readframes(nf)
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(sw, np.int16)
    arr = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if sw == 1:
        arr = (arr - 128.0) / 128.0
    elif sw == 2:
        arr /= 32768.0
    elif sw == 4:
        arr /= 2147483648.0
    if nch > 1:
        arr = arr.reshape(-1, nch).mean(axis=1)
    return arr.astype(np.float64), sr


def _resample(x: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return x
    n_dst = int(round(len(x) * dst_sr / src_sr))
    src_t = np.arange(len(x)) / src_sr
    dst_t = np.arange(n_dst) / dst_sr
    return np.interp(dst_t, src_t, x)


# ---------------------------------------------------------------------------
# Azure Neural TTS
# ---------------------------------------------------------------------------
def _wrap_ssml(body: str, voice: str, locale: str = "en-US") -> str:
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{locale}">'
        f'<voice name="{voice}">'
        f'{body}'
        f'</voice>'
        f'</speak>'
    )


def _azure_synth(jobs: list[tuple[str, Path]],
                 key: str, region: str, voice: str) -> bool:
    """Synthesize each (ssml_body, output_path) using Azure neural TTS.

    Returns True on full success, False on any failure (caller falls back).
    """
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        print("[narration] azure-cognitiveservices-speech not installed.")
        return False

    cfg = speechsdk.SpeechConfig(subscription=key, region=region)
    # 24 kHz mono PCM — high enough for narration, light enough to mux fast.
    cfg.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
    )

    for body, out_path in jobs:
        ssml = _wrap_ssml(body, voice)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        audio_cfg = speechsdk.audio.AudioOutputConfig(filename=str(out_path))
        synth = speechsdk.SpeechSynthesizer(speech_config=cfg,
                                            audio_config=audio_cfg)
        try:
            result = synth.speak_ssml_async(ssml).get()
        except Exception as exc:  # noqa: BLE001
            print(f"[narration] Azure synth raised for line "
                  f"({body[:40]}...): {exc}")
            return False
        reason = result.reason
        if reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            details = f" reason={reason}"
            try:
                if reason == speechsdk.ResultReason.Canceled:
                    cd = speechsdk.CancellationDetails(result)
                    details = f" [{cd.reason}: {cd.error_details}]"
            except Exception:  # noqa: BLE001
                pass
            # If file was nevertheless written, accept it.
            if out_path.exists() and out_path.stat().st_size > 1000:
                print(f"[narration] non-Completed reason but file written: "
                      f"{out_path.name}{details}")
                continue
            print(f"[narration] Azure synth failed for line "
                  f"({body[:40]}...){details}")
            return False
    return True


# ---------------------------------------------------------------------------
# Windows SAPI fallback
# ---------------------------------------------------------------------------
def _sapi_synth(jobs: list[tuple[str, Path]]) -> bool:
    """jobs: (plain_text, output_wav). Uses Microsoft David Desktop."""
    if not jobs:
        return True
    lines = [
        "Add-Type -AssemblyName System.Speech",
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        "try { $s.SelectVoice('Microsoft David Desktop') } catch {}",
        "$s.Rate = -2",
        "$s.Volume = 100",
    ]
    for text, path in jobs:
        safe_text = text.replace("'", "''")
        safe_path = str(path).replace("'", "''")
        lines.append(f"$s.SetOutputToWaveFile('{safe_path}')")
        lines.append(f"$s.Speak('{safe_text}')")
    lines.append("$s.Dispose()")
    script = "\n".join(lines)

    with tempfile.NamedTemporaryFile("w", suffix=".ps1",
                                     delete=False, encoding="utf-8") as fp:
        fp.write(script)
        ps_path = fp.name
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", ps_path],
            check=True, capture_output=True, text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"[narration] SAPI fallback failed: {exc}")
        return False
    finally:
        try:
            os.unlink(ps_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Narration assembly
# ---------------------------------------------------------------------------
def render_narration() -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Returns (narration_track_at_SR, [(t_start, t_end), ...])."""
    n = int(DURATION_S * SR)
    track = np.zeros(n, dtype=np.float64)
    windows: list[tuple[float, float]] = []

    tmpdir = Path(tempfile.mkdtemp(prefix="bg_narr_"))
    try:
        ssml_jobs: list[tuple[str, Path]] = []
        sapi_jobs: list[tuple[str, Path]] = []
        files: list[Path] = []
        for i, (_t, ssml_body, plain, _g) in enumerate(NARRATION):
            p = tmpdir / f"line_{i:02d}.wav"
            files.append(p)
            ssml_jobs.append((ssml_body, p))
            sapi_jobs.append((plain, p))

        ok = False
        key, region, voice = _azure_creds()
        if key and region:
            print(f"[narration] using Azure neural voice: {voice}")
            ok = _azure_synth(ssml_jobs, key, region, voice)
            if not ok:
                print("[narration] Azure failed, falling back to SAPI.")
        else:
            print("[narration] AZURE_SPEECH_KEY/REGION not set, "
                  "using Windows SAPI.")

        if not ok:
            ok = _sapi_synth(sapi_jobs)
        if not ok:
            return track, windows

        for idx, ((start, _ssml, _plain, gain), path) in enumerate(
                zip(NARRATION, files)):
            if not path.exists() or path.stat().st_size < 100:
                print(f"[narration] missing: {path}")
                continue
            voice_arr, sr = _read_wav_mono(path)
            voice_arr = _resample(voice_arr, sr, SR)
            peak = float(np.max(np.abs(voice_arr)) or 1.0)
            voice_arr = voice_arr / peak * 0.95 * gain

            # Hard guarantee: a line must end before the next line begins,
            # with a small breath-gap. If it would overrun, trim with a
            # short fade-out so we never hear two narrators at once.
            gap_s = 0.04
            next_start = (NARRATION[idx + 1][0] if idx + 1 < len(NARRATION)
                          else DURATION_S)
            max_dur = max(0.1, next_start - start - gap_s)
            max_samples = int(max_dur * SR)
            if len(voice_arr) > max_samples:
                fade_n = min(int(0.08 * SR), max_samples // 4)
                voice_arr = voice_arr[:max_samples].copy()
                if fade_n > 0:
                    fade = np.linspace(1.0, 0.0, fade_n)
                    voice_arr[-fade_n:] *= fade
                print(f"[narration] line {idx} trimmed to {max_dur:.2f}s "
                      f"to avoid overlapping line {idx + 1}")

            i0 = int(start * SR)
            end = min(n, i0 + len(voice_arr))
            track[i0:end] += voice_arr[: end - i0]
            windows.append((start, start + (end - i0) / SR))
    finally:
        for p in tmpdir.glob("*"):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            tmpdir.rmdir()
        except OSError:
            pass
    return track, windows


# ---------------------------------------------------------------------------
# Mix + ducking + write
# ---------------------------------------------------------------------------
def _smooth(x: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return x
    k = np.ones(win) / win
    return np.convolve(x, k, mode="same")


def build_duck_envelope(narr: np.ndarray, windows: list[tuple[float, float]],
                        depth: float = 0.55) -> np.ndarray:
    """1.0 normally, dipped under spoken windows."""
    duck = np.ones_like(narr)
    if not windows:
        return duck
    pad = 0.18
    fade = 0.18
    for s, e in windows:
        s_pad = max(0.0, s - pad)
        e_pad = min(DURATION_S, e + pad)
        i0 = int(s_pad * SR)
        i1 = int(e_pad * SR)
        ramp = max(1, int(fade * SR))
        for i in range(i0, i1):
            if i < i0 + ramp:
                v = (i - i0) / ramp
            elif i > i1 - ramp:
                v = (i1 - i) / ramp
            else:
                v = 1.0
            mul = 1.0 - depth * max(0.0, min(1.0, v))
            duck[i] = min(duck[i], mul)
    return duck


def normalize(x: np.ndarray, target_peak: float = 0.92) -> np.ndarray:
    peak = float(np.max(np.abs(x)) or 1.0)
    if peak > target_peak:
        x = x / peak * target_peak
    return x


def soft_clip(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)


def write_wav_mono(path: Path, samples: np.ndarray) -> None:
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def render(out_path: Path = DEFAULT_OUT) -> Path:
    print("[audio] synthesizing music...")
    music = synth_music(DURATION_S)
    print("[audio] rendering narration...")
    narration, windows = render_narration()
    if windows:
        print(f"[audio] {len(windows)} narration line(s) placed.")
    else:
        print("[audio] no narration — music only.")

    print("[audio] mixing + ducking...")
    duck = build_duck_envelope(narration, windows, depth=0.55)
    duck = _smooth(duck, win=int(0.04 * SR))
    mix = music * duck + narration * 1.05

    mix = soft_clip(mix * 1.05) * 0.95
    mix = normalize(mix, target_peak=0.92)

    write_wav_mono(out_path, mix)
    size_kb = out_path.stat().st_size / 1024
    print(f"[audio] wrote {out_path} ({size_kb:.0f} KB)")
    return out_path


if __name__ == "__main__":
    render()
