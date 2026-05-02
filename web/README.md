# Babel's Glyph — Web build

Same game, same code, but compiled to WebAssembly via [pygbag](https://pygame-web.github.io/) so it runs in any modern browser on any OS — no install.

## Test locally

```powershell
.\build-web.bat            # build static bundle into build\web\
# or, to build + start a test server in one go:
C:\Users\kakrishna\.babelsglyph-web-venv\Scripts\python.exe -m pygbag .
```

Then open http://localhost:8000 in Chrome/Edge/Firefox. Press **F11** for fullscreen.

> The first load downloads the Python+pygame WASM runtime from the pygame-web CDN (~5–8 MB, cached by the browser after).

## Deploy

Upload the entire **`build/web/`** folder anywhere that serves static files:

| Host | How |
|---|---|
| **itch.io** (recommended) | Create a project, set kind = HTML, drag-drop a zip of `build/web/`, tick "This file will be played in the browser", set viewport to 960 × 544 + tick fullscreen button. |
| **GitHub Pages** | Commit `build/web/` to a repo, enable Pages on the branch & folder. Done. |
| **Netlify Drop** | https://app.netlify.com/drop — drag `build/web/` onto the page; you get an instant URL. |
| **Cloudflare Pages / Vercel / S3** | Any static host works. |

## Files

- `main.py` — same game as desktop, but the loop is `async` with `await asyncio.sleep(0)` per frame so it cooperates with the browser event loop.
- `game/` — gameplay modules (unchanged from desktop build).
- `pygbag.ini` — build config.
- `build-web.bat` — one-click rebuild.

## Controls

A/D run · Space jump (twice for double jump) · Shift dash · S slide · E glyph bomb · R restart
