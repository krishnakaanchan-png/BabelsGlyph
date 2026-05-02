# Babel's Glyph

A side-scrolling endless runner with an **Ancient Technology** theme — sprint a hooded scribe through three crumbling zones (Sandstone Ruins, Forge of Embers, Clockwork Workshop), dodge traps, and collect glyphs to power the great obelisk.

All graphics are procedurally generated in code — no external art assets, no audio dependencies. Built with [pygame-ce](https://pyga.me/).

![status](https://img.shields.io/badge/built%20with-pygame--ce-blue) ![python](https://img.shields.io/badge/python-3.12-blue)

## Two builds

| Folder | Target | How to run |
|---|---|---|
| [`desktop/`](desktop/) | Windows `.exe` (PyInstaller) | `desktop/build.bat`, then run `dist/BabelsGlyph/BabelsGlyph.exe` |
| [`web/`](web/) | Browser (WebAssembly via [pygbag](https://pygame-web.github.io/)) | `web/build-web.bat`, then open `http://localhost:8000` |

The two folders share an almost-identical `game/` package; the web `main.py` is the async-wrapped variant required by pygbag.

## Controls

- **A / D** or **←/→** — move
- **Space / W / ↑** — jump (hold for higher jump)
- **Esc** — quit (or return to title screen on web)
- **R** — restart after game over

## Quick start (desktop)

```powershell
cd desktop
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Quick start (web, local)

```powershell
cd web
py -3.12 -m venv C:\Users\<you>\.babelsglyph-web-venv   # keep venv OUTSIDE the project folder
C:\Users\<you>\.babelsglyph-web-venv\Scripts\Activate.ps1
pip install pygame-ce pygbag
python -m pygbag --port 8000 .
```

Then open <http://localhost:8000> in a browser.

## Project layout

```
BabelsGlyph/
├── desktop/         # PyInstaller-packaged Windows build
│   ├── main.py
│   ├── game/        # constants, render, input, world, chunks,
│   │                # entities, player, hud, particles
│   ├── build.bat
│   └── requirements.txt
└── web/             # pygbag (WebAssembly) build
    ├── main.py      # async-wrapped variant
    ├── game/        # same modules as desktop
    ├── pygbag.ini
    ├── build-web.bat
    └── requirements.txt
```

## Theme

**Ancient Technology** — three biome zones blend Bronze-Age stone with steampunk machinery:
- **Sandstone Ruins** — sun-baked obelisks, falling pillars, hieroglyph plates
- **Forge of Embers** — magma vents, drifting smoke, chain-driven hammers
- **Clockwork Workshop** — gear platforms, swinging pendulums, brass conduits

## License

MIT
