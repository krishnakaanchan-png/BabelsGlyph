"""Global leaderboard backed by a public jsonblob.com bin.

Architecture:
  * Single shared bin URL (api.jsonblob.com supports CORS).
  * Local cache mirrors the last successful fetch so the UI has data instantly
    on next launch (and stays usable offline).
  * Network I/O happens off the game loop:
      - Desktop: background ``threading.Thread`` using ``urllib.request``.
      - Web (pygbag/emscripten): ``asyncio`` task that calls JavaScript
        ``fetch`` via a tiny JS-side helper installed at import time. We
        deliberately avoid ``pyodide.http`` (not bundled with pygbag), the
        urllib monkey-patch (routes through a non-existent WebSocket bridge
        and fails for arbitrary public APIs), and direct ``await js.fetch(...)``
        (its returned Promise has no asyncio loop binding in pygbag's CPython).
  * Submits are GET-modify-PUT with conditional ``If-Match`` on the ETag and
    one retry on conflict. The local cache is updated optimistically so the
    player sees their name immediately.

Score record schema:
    {"name": str, "distance_m": int, "glyphs": int, "ts": int (unix seconds)}

The bin (``BIN_URL``) was created via the jsonblob.com REST API. No API key
is required for read or write. To rotate the backing store, edit ``BIN_URL``.
"""
from __future__ import annotations
import json
import sys
import threading
import time
from pathlib import Path


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
BIN_URL = "https://api.jsonblob.com/019e0989-8fbc-7830-b6f6-068812f476f2"
TOP_N = 100              # we keep up to this many scores in the bin
DEFAULT_REQUEST_TIMEOUT = 10.0
REFRESH_INTERVAL_S = 30.0  # client-side cooldown between auto-refetches

_WEB = sys.platform == "emscripten"


def _cache_path() -> Path:
    if _WEB:
        return Path("leaderboard_cache.json")
    return Path.home() / ".babels-glyph" / "leaderboard_cache.json"


# ----------------------------------------------------------------------
# Low-level HTTP helpers
# ----------------------------------------------------------------------
def _sync_request(method: str, url: str, body: bytes | None = None,
                  if_match: str | None = None) -> tuple[int, str, str | None]:
    """Plain blocking HTTP call. Returns (status, body_text, etag)."""
    import urllib.request
    import urllib.error
    headers: dict[str, str] = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if if_match:
        headers["If-Match"] = if_match
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_REQUEST_TIMEOUT) as r:
            text = r.read().decode("utf-8", errors="replace")
            etag = r.headers.get("ETag")
            return r.status, text, etag
    except urllib.error.HTTPError as e:
        try:
            text = e.read().decode("utf-8", errors="replace")
        except Exception:
            text = ""
        return e.code, text, None


# Pygbag's CPython does not ship `pyodide.http`, and `js.fetch` returns a
# Promise that asyncio cannot await directly (`'browser.PromiseWrapper' has
# no attribute '_loop'`). The supported pattern in pygbag is the one used by
# `platform.window.cross_file`: call JS `fetch`, drive the returned Promise
# via a JS generator that yields until resolution, and consume that generator
# with `platform.jsiter` (a true asyncio-friendly coroutine helper). We
# install our own helper once, then call it for both GET and PUT.
_WEB_HELPER_INSTALLED = False
_WEB_HELPER_NAME = "bg_leaderboard_fetch"
_WEB_HELPER_JS = """
window.""" + _WEB_HELPER_NAME + """ = function(url, init) {
    var done = null;
    var error = null;
    var result = null;
    fetch(url, init || {})
        .then(function(resp) {
            result = { status: resp.status,
                       etag: resp.headers.get('ETag') };
            return resp.text();
        })
        .then(function(text) { result.text = text; done = true; })
        .catch(function(e) { error = String(e); done = true; });
    return (function*() {
        while (!done) yield null;
        if (error) throw new Error(error);
        yield result;
    })();
};
"""


def _ensure_web_helper() -> None:
    global _WEB_HELPER_INSTALLED
    if _WEB_HELPER_INSTALLED:
        return
    import platform  # type: ignore - pygbag's emscripten platform module
    platform.eval(_WEB_HELPER_JS)
    _WEB_HELPER_INSTALLED = True


async def _async_request(method: str, url: str, body: bytes | None = None,
                         if_match: str | None = None) -> tuple[int, str, str | None]:
    """Async HTTP for the web build via JavaScript ``fetch``."""
    import platform  # type: ignore
    import json as _json
    _ensure_web_helper()

    headers: dict[str, str] = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if if_match:
        headers["If-Match"] = if_match

    init_dict: dict = {"method": method}
    if headers:
        init_dict["headers"] = headers
    if body is not None:
        init_dict["body"] = (
            body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body
        )

    # Convert the Python dict to a real JS object via JSON round-trip; this
    # avoids pygbag's "object of type 'list' cannot be converted" errors that
    # happen when a Python dict containing nested dicts is passed straight to
    # a JS function.
    if init_dict:
        init_js = platform.window.JSON.parse(_json.dumps(init_dict))
    else:
        init_js = None

    helper = getattr(platform.window, _WEB_HELPER_NAME)
    gen = helper(url, init_js)
    result = await platform.jsiter(gen)
    if result is None:
        return 0, "", None
    status = int(result.status)
    text = str(result.text) if result.text is not None else ""
    etag = result.etag
    if etag is not None:
        etag = str(etag)
    return status, text, etag


# ----------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------
_INSTANCE: "Leaderboard | None" = None


def init() -> None:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = Leaderboard()
        _INSTANCE.start()


def get() -> "Leaderboard":
    if _INSTANCE is None:
        init()
    assert _INSTANCE is not None
    return _INSTANCE


# ----------------------------------------------------------------------
class Leaderboard:
    """Thread-safe, network-tolerant top-scores list."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scores: list[dict] = []
        self._etag: str | None = None
        self._last_fetch_t: float = 0.0
        self._fetching: bool = False
        self._submitting: bool = False
        self._last_error: str | None = None
        # Load cache so the UI has something to display immediately.
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        self.refresh()

    def refresh(self, force: bool = False) -> None:
        """Schedule a refetch (no-op if one is already in flight or recent)."""
        with self._lock:
            if self._fetching:
                return
            if not force and (time.time() - self._last_fetch_t) < REFRESH_INTERVAL_S:
                return
            self._fetching = True
        self._dispatch_fetch()

    def submit(self, name: str, distance_m: int, glyphs: int) -> None:
        """Record a new run and upload it. Always updates the local cache first."""
        entry = {
            "name": str(name)[:24],
            "distance_m": int(max(0, distance_m)),
            "glyphs": int(max(0, glyphs)),
            "ts": int(time.time()),
        }
        with self._lock:
            self._scores.append(entry)
            self._scores = self._sort_trim(self._scores)
            snapshot = list(self._scores)
        self._save_cache(snapshot)
        self._dispatch_submit(entry)

    def top(self, n: int = 10) -> list[dict]:
        with self._lock:
            return list(self._scores[:n])

    def is_top(self, distance_m: int, n: int = 10) -> bool:
        with self._lock:
            if len(self._scores) < n:
                return True
            return distance_m > int(self._scores[n - 1].get("distance_m", 0))

    def status(self) -> str:
        """One-word UI hint."""
        with self._lock:
            if self._fetching:
                return "syncing"
            if self._submitting:
                return "uploading"
            if self._last_error:
                return "offline"
            if self._scores:
                return "online"
            return "..."

    # ------------------------------------------------------------------
    # Dispatch (desktop = thread, web = asyncio task)
    # ------------------------------------------------------------------
    def _dispatch_fetch(self) -> None:
        if _WEB:
            self._spawn_task(self._fetch_async())
        else:
            threading.Thread(target=self._fetch_sync, daemon=True).start()

    def _dispatch_submit(self, entry: dict) -> None:
        if _WEB:
            self._spawn_task(self._submit_async(entry))
        else:
            threading.Thread(target=self._submit_sync, args=(entry,),
                             daemon=True).start()

    @staticmethod
    def _spawn_task(coro) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.create_task(coro)

    # ------------------------------------------------------------------
    # Sync workers (desktop)
    # ------------------------------------------------------------------
    def _fetch_sync(self) -> None:
        try:
            status, text, etag = _sync_request("GET", BIN_URL)
            self._absorb_fetch_result(status, text, etag)
        except Exception as e:  # noqa: BLE001 - network is best-effort
            with self._lock:
                self._last_error = repr(e)
        finally:
            with self._lock:
                self._fetching = False

    def _submit_sync(self, entry: dict) -> None:
        with self._lock:
            self._submitting = True
        try:
            for attempt in range(2):
                status, text, etag = _sync_request("GET", BIN_URL)
                payload = self._build_put_payload(status, text, entry)
                put_status, _, new_etag = _sync_request(
                    "PUT", BIN_URL, body=payload, if_match=etag
                )
                if self._absorb_submit_result(put_status, payload, new_etag):
                    return
                if put_status == 412 and attempt == 0:
                    continue  # ETag conflict — retry once.
                return
        except Exception as e:  # noqa: BLE001
            with self._lock:
                self._last_error = repr(e)
        finally:
            with self._lock:
                self._submitting = False

    # ------------------------------------------------------------------
    # Async workers (web)
    # ------------------------------------------------------------------
    async def _fetch_async(self) -> None:
        try:
            status, text, etag = await _async_request("GET", BIN_URL)
            self._absorb_fetch_result(status, text, etag)
        except Exception as e:  # noqa: BLE001
            with self._lock:
                self._last_error = repr(e)
        finally:
            with self._lock:
                self._fetching = False

    async def _submit_async(self, entry: dict) -> None:
        with self._lock:
            self._submitting = True
        try:
            for attempt in range(2):
                status, text, etag = await _async_request("GET", BIN_URL)
                payload = self._build_put_payload(status, text, entry)
                put_status, _, new_etag = await _async_request(
                    "PUT", BIN_URL, body=payload, if_match=etag
                )
                if self._absorb_submit_result(put_status, payload, new_etag):
                    return
                if put_status == 412 and attempt == 0:
                    continue
                return
        except Exception as e:  # noqa: BLE001
            with self._lock:
                self._last_error = repr(e)
        finally:
            with self._lock:
                self._submitting = False

    # ------------------------------------------------------------------
    # Shared post-processing
    # ------------------------------------------------------------------
    def _absorb_fetch_result(self, status: int, text: str,
                             etag: str | None) -> None:
        if status != 200:
            with self._lock:
                self._last_error = f"GET {status}"
            return
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            data = {}
        remote = data.get("scores", []) if isinstance(data, dict) else []
        with self._lock:
            self._scores = self._sort_trim(self._merge(self._scores, remote))
            self._etag = etag
            self._last_fetch_t = time.time()
            self._last_error = None
            snapshot = list(self._scores)
        self._save_cache(snapshot)

    def _build_put_payload(self, get_status: int, get_text: str,
                           new_entry: dict) -> bytes:
        if get_status == 200 and get_text:
            try:
                data = json.loads(get_text)
            except ValueError:
                data = {}
            remote = data.get("scores", []) if isinstance(data, dict) else []
        else:
            remote = []
        merged = self._sort_trim(self._merge(remote, [new_entry]))
        return json.dumps({"scores": merged}).encode("utf-8")

    def _absorb_submit_result(self, put_status: int, payload: bytes,
                              new_etag: str | None) -> bool:
        if put_status != 200:
            return False
        try:
            data = json.loads(payload.decode("utf-8"))
        except ValueError:
            data = {"scores": []}
        scores = data.get("scores", []) if isinstance(data, dict) else []
        with self._lock:
            self._scores = self._sort_trim(scores)
            self._etag = new_etag
            self._last_fetch_t = time.time()
            self._last_error = None
            snapshot = list(self._scores)
        self._save_cache(snapshot)
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _sort_trim(scores: list[dict]) -> list[dict]:
        valid: list[dict] = []
        for s in scores:
            if not isinstance(s, dict):
                continue
            try:
                d = int(s.get("distance_m", 0))
            except (TypeError, ValueError):
                continue
            if d <= 0:
                continue
            n = str(s.get("name", "")).strip() or "Player"
            valid.append({
                "name": n[:24],
                "distance_m": d,
                "glyphs": int(s.get("glyphs", 0) or 0),
                "ts": int(s.get("ts", 0) or 0),
            })
        # Keep only each player's personal best. We compare names
        # case-insensitively after trimming so "kk", "KK" and " kk "
        # all collapse onto the same row. Tie-breaker on equal distance:
        # the more recent timestamp wins (so the leaderboard reflects
        # the player's latest matching record).
        best_by_name: dict[str, dict] = {}
        for s in valid:
            key = s["name"].casefold()
            cur = best_by_name.get(key)
            if (cur is None
                    or s["distance_m"] > cur["distance_m"]
                    or (s["distance_m"] == cur["distance_m"]
                        and s["ts"] > cur["ts"])):
                best_by_name[key] = s
        deduped = list(best_by_name.values())
        deduped.sort(key=lambda s: (-s["distance_m"], -s["ts"]))
        return deduped[:TOP_N]

    @staticmethod
    def _merge(a: list[dict], b: list[dict]) -> list[dict]:
        # Dedupe by (name, distance, ts) tuple.
        seen: dict[tuple, dict] = {}
        for s in (a + b):
            if not isinstance(s, dict):
                continue
            key = (str(s.get("name", "")), int(s.get("distance_m", 0) or 0),
                   int(s.get("ts", 0) or 0))
            seen[key] = s
        return list(seen.values())

    def _load_cache(self) -> None:
        try:
            with _cache_path().open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                scores = data.get("scores", [])
                if isinstance(scores, list):
                    self._scores = self._sort_trim(scores)
        except (OSError, ValueError):
            pass

    @staticmethod
    def _save_cache(scores: list[dict]) -> None:
        try:
            p = _cache_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as f:
                json.dump({"scores": scores}, f)
        except OSError:
            pass
