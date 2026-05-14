"""Player profile (just a name, persisted across runs).

Storage strategy:
  * Desktop: ~/.babels-glyph/profile.json
  * Web (pygbag/emscripten): profile.json in the working directory.
    pygbag persists CWD via IndexedDB, so the name survives reloads.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


_NAME_MAX = 12
_NAME_MIN = 1
_state: dict | None = None  # cached in-memory copy


def _profile_path() -> Path:
    if sys.platform == "emscripten":
        return Path("profile.json")
    return Path.home() / ".babels-glyph" / "profile.json"


def _load() -> dict:
    global _state
    if _state is not None:
        return _state
    p = _profile_path()
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _state = data
            return _state
    except (OSError, ValueError):
        pass
    _state = {}
    return _state


def _save() -> None:
    if _state is None:
        return
    p = _profile_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(_state, f)
    except OSError:
        # Read-only filesystem (e.g. some browser sandboxes) — silently ignore.
        pass


def sanitize(raw: str) -> str:
    """Trim, drop control chars, clamp length, fall back to 'Player'."""
    if not raw:
        return ""
    cleaned = "".join(ch for ch in raw if ch.isprintable() and ch != "\t")
    cleaned = cleaned.strip()
    if len(cleaned) > _NAME_MAX:
        cleaned = cleaned[:_NAME_MAX]
    return cleaned


def has_name() -> bool:
    name = _load().get("name")
    return isinstance(name, str) and len(sanitize(name)) >= _NAME_MIN


def get_name() -> str:
    name = sanitize(_load().get("name", "") or "")
    return name if name else "Player"


def set_name(raw: str) -> str:
    """Validate, store, persist. Returns the canonical stored name."""
    cleaned = sanitize(raw) or "Player"
    state = _load()
    state["name"] = cleaned
    _save()
    return cleaned


def name_max_len() -> int:
    return _NAME_MAX
