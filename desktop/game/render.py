"""Color palette, draw helpers, PyInstaller-safe resource path."""
from __future__ import annotations
import math
import os
import random
import sys

import pygame

# Ancient palette.
SANDSTONE     = (216, 179, 117)
SANDSTONE_D   = (168, 132, 80)
SAND_LIGHT    = (236, 206, 152)
SKY_DAWN_TOP  = (252, 218, 158)
SKY_DAWN_BOT  = (210, 130, 90)
SKY_FORGE_TOP = (90, 50, 60)
SKY_FORGE_BOT = (200, 80, 50)
SKY_WORK_TOP  = (170, 200, 220)
SKY_WORK_BOT  = (220, 220, 200)
LAPIS         = (28, 74, 138)
LAPIS_LIGHT   = (60, 120, 200)
COPPER        = (184, 115, 51)
COPPER_LIGHT  = (220, 160, 90)
EMBER         = (255, 122, 43)
EMBER_DIM     = (180, 70, 20)
STONE         = (90, 78, 64)
STONE_DARK    = (52, 45, 38)
STONE_LIGHT   = (140, 122, 100)
BONE          = (236, 220, 188)
BLOOD         = (170, 40, 40)
GLYPH_GLOW    = (255, 210, 110)
GLYPH_GLOW_S  = (255, 244, 180)
BEAM_CORE     = (255, 240, 200)
CHARGE_FULL   = (110, 220, 130)
CHARGE_LOW    = (220, 80, 60)
HEART_RED     = (220, 60, 70)
GEAR_BRONZE   = (180, 120, 60)
GEAR_BRONZE_D = (110, 70, 30)
STEAM_WHITE   = (240, 240, 240)
PARCHMENT     = (228, 208, 160)
INK           = (60, 40, 30)
WORKSHOP_GREEN= (80, 130, 90)
TITLE_INK     = (16, 10, 8)
TITLE_GOLD_D  = (150, 75, 22)
TITLE_GOLD    = (255, 196, 66)
TITLE_GOLD_HI = (255, 246, 184)


_TITLE_BG_CACHE: dict[tuple[int, int], pygame.Surface] = {}
_TITLE_LOGO_CACHE: dict[int, pygame.Surface | None] = {}
_ASSET_CACHE: dict[tuple[str, bool], pygame.Surface | None] = {}
_ASSET_SCALE_CACHE: dict[tuple[str, int, int, bool, bool], pygame.Surface | None] = {}
_SHEET_FRAME_CACHE: dict[tuple[str, int, int, int], pygame.Surface | None] = {}


def resource_path(rel: str) -> str:
    """Resolve a path that works both in dev and inside a PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__) + "/.."))
    return os.path.join(base, rel)


def lerp_color(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _fallback_title_background(w: int, h: int) -> pygame.Surface:
    s = pygame.Surface((w, h)).convert()
    horizon = int(h * 0.68)
    for y in range(h):
        t = y / h
        if t < 0.48:
            c = lerp_color((16, 13, 28), (98, 42, 34), t / 0.48)
        else:
            c = lerp_color((238, 116, 30), (48, 29, 22), (t - 0.48) / 0.52)
        pygame.draw.line(s, c, (0, y), (w, y))

    glow = pygame.Surface((w, h), pygame.SRCALPHA)
    for r in range(int(w * 0.42), 12, -18):
        a = int(120 * (1 - r / (w * 0.42)) ** 1.7)
        pygame.draw.circle(glow, (255, 181, 58, a), (w // 2, horizon), r)
    s.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    rng = random.Random(1848)
    stars = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(520):
        x = rng.randrange(w)
        y = rng.randrange(0, int(h * 0.55))
        pygame.draw.circle(stars, (255, 230, 170, rng.randint(55, 190)), (x, y), rng.choice([1, 1, 1, 2]))
    s.blit(stars, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def block(x, base_y, bw, bh, col):
        rect = pygame.Rect(x, base_y - bh, bw, bh)
        pygame.draw.rect(s, col, rect)
        pygame.draw.rect(s, (42, 25, 18), rect, 1)
        pygame.draw.line(s, (214, 112, 38), rect.topleft, rect.topright, 1)
        for yy in range(rect.top + 12, rect.bottom, 22):
            pygame.draw.line(s, (82, 45, 28), (rect.left, yy), (rect.right, yy), 1)

    for x in range(-30, w + 80, 88):
        block(x, horizon + rng.randint(28, 82), rng.randint(54, 120), rng.randint(70, 170), (84, 48, 31))
    for x in range(-50, w + 100, 120):
        block(x, h + rng.randint(-18, 20), rng.randint(88, 180), rng.randint(90, 220), (52, 32, 24))

    for y in range(h):
        d = abs(y - h * 0.52) / (h * 0.52)
        a = int(max(0, (d ** 1.8) * 95))
        pygame.draw.line(s, (0, 0, 0, a), (0, y), (w, y))
    return s


def _cover_scale(src: pygame.Surface, w: int, h: int) -> pygame.Surface:
    sw, sh = src.get_size()
    scale = max(w / sw, h / sh)
    tw = max(w, int(sw * scale))
    th = max(h, int(sh * scale))
    scaled = pygame.transform.smoothscale(src, (tw, th))
    x = (tw - w) // 2
    y = (th - h) // 2
    return scaled.subsurface(pygame.Rect(x, y, w, h)).copy()


def get_asset(name: str, *, alpha: bool = True) -> pygame.Surface | None:
    key = (name, alpha)
    if key in _ASSET_CACHE:
        return _ASSET_CACHE[key]
    path = resource_path(f"assets/{name}")
    try:
        img = pygame.image.load(path)
        img = img.convert_alpha() if alpha else img.convert()
    except Exception:
        img = None
    _ASSET_CACHE[key] = img
    return img


def get_scaled_asset(name: str, w: int, h: int, *, alpha: bool = True,
                     cover: bool = False) -> pygame.Surface | None:
    key = (name, w, h, alpha, cover)
    if key in _ASSET_SCALE_CACHE:
        return _ASSET_SCALE_CACHE[key]
    src = get_asset(name, alpha=alpha)
    if src is None:
        _ASSET_SCALE_CACHE[key] = None
        return None
    if cover:
        out = _cover_scale(src, w, h)
    else:
        sw, sh = src.get_size()
        scale = min(w / sw, h / sh)
        out = pygame.transform.smoothscale(src, (max(1, int(sw * scale)), max(1, int(sh * scale))))
    _ASSET_SCALE_CACHE[key] = out
    return out


def get_sheet_frame(name: str, cols: int, rows: int, index: int) -> pygame.Surface | None:
    key = (name, cols, rows, index)
    if key in _SHEET_FRAME_CACHE:
        return _SHEET_FRAME_CACHE[key]
    sheet = get_asset(name, alpha=True)
    if sheet is None:
        _SHEET_FRAME_CACHE[key] = None
        return None
    fw = sheet.get_width() // cols
    fh = sheet.get_height() // rows
    col = index % cols
    row = (index // cols) % rows
    frame = sheet.subsurface(pygame.Rect(col * fw, row * fh, fw, fh)).copy()
    _SHEET_FRAME_CACHE[key] = frame
    return frame


def draw_asset_contain(surf: pygame.Surface, name: str, rect: pygame.Rect,
                       *, alpha: bool = True) -> bool:
    img = get_scaled_asset(name, rect.width, rect.height, alpha=alpha, cover=False)
    if img is None:
        return False
    surf.blit(img, (rect.centerx - img.get_width() // 2, rect.centery - img.get_height() // 2))
    return True


def draw_asset_cover(surf: pygame.Surface, name: str, rect: pygame.Rect,
                     *, alpha: bool = False) -> bool:
    img = get_scaled_asset(name, rect.width, rect.height, alpha=alpha, cover=True)
    if img is None:
        return False
    surf.blit(img, rect.topleft)
    return True


def get_title_background(w: int, h: int) -> pygame.Surface:
    key = (w, h)
    if key in _TITLE_BG_CACHE:
        return _TITLE_BG_CACHE[key]
    path = resource_path("assets/title_bg.png")
    try:
        src = pygame.image.load(path).convert()
        bg = _cover_scale(src, w, h)
    except Exception:
        bg = _fallback_title_background(w, h)
    _TITLE_BG_CACHE[key] = bg
    return bg


def get_title_logo(width: int) -> pygame.Surface | None:
    if width in _TITLE_LOGO_CACHE:
        return _TITLE_LOGO_CACHE[width]
    path = resource_path("assets/title_logo.png")
    try:
        src = pygame.image.load(path).convert_alpha()
        sw, sh = src.get_size()
        height = max(1, int(sh * (width / sw)))
        logo = pygame.transform.smoothscale(src, (width, height))
    except Exception:
        logo = None
    _TITLE_LOGO_CACHE[width] = logo
    return logo


def draw_letterbox(surf: pygame.Surface, height: int = 22, alpha: int = 150) -> None:
    w, h = surf.get_size()
    band = pygame.Surface((w, height), pygame.SRCALPHA)
    band.fill((0, 0, 0, alpha))
    surf.blit(band, (0, 0))
    surf.blit(band, (0, h - height))


def glow_text(surf: pygame.Surface, font: pygame.font.Font, text: str,
              center: tuple[int, int], *, fill=TITLE_GOLD,
              glow=GLYPH_GLOW, shadow=TITLE_INK, radius: int = 4) -> pygame.Rect:
    base = font.render(text, True, fill)
    rect = base.get_rect(center=center)
    for off in range(radius, 0, -1):
        a = max(20, 34 - off * 3)
        for dx, dy in ((-off, 0), (off, 0), (0, -off), (0, off)):
            halo = font.render(text, True, glow)
            halo.set_alpha(a)
            surf.blit(halo, rect.move(dx, dy))
    rim = font.render(text, True, TITLE_GOLD_D)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        surf.blit(rim, rect.move(dx, dy))
    sh = font.render(text, True, shadow)
    surf.blit(sh, rect.move(3, 4))
    surf.blit(base, rect)
    hi = font.render(text, True, TITLE_GOLD_HI)
    hi.set_alpha(120)
    surf.blit(hi, rect.move(-1, -1))
    return rect


def carved_panel(surf: pygame.Surface, rect: pygame.Rect, *,
                 fill=(42, 24, 14, 212), border=TITLE_GOLD_D,
                 glow_alpha: int = 50) -> None:
    bg = pygame.Surface(rect.size, pygame.SRCALPHA)
    for y in range(rect.height):
        t = y / max(1, rect.height - 1)
        c = lerp_color((fill[0] + 30, fill[1] + 18, fill[2] + 8), fill[:3], t)
        pygame.draw.line(bg, (*c, fill[3]), (0, y), (rect.width, y))
    rng = random.Random(rect.x * 37 + rect.y * 19 + rect.width)
    for _ in range(max(18, rect.width * rect.height // 1800)):
        x = rng.randrange(rect.width)
        y = rng.randrange(rect.height)
        bg.set_at((x, y), (255, 205, 120, rng.randint(18, 48)))
    surf.blit(bg, rect.topleft)

    if glow_alpha:
        halo = pygame.Surface((rect.width + 18, rect.height + 18), pygame.SRCALPHA)
        pygame.draw.rect(halo, (*GLYPH_GLOW, glow_alpha), halo.get_rect(), 2)
        surf.blit(halo, (rect.x - 9, rect.y - 9), special_flags=pygame.BLEND_RGBA_ADD)
    pygame.draw.rect(surf, border, rect, 2)
    pygame.draw.rect(surf, GLYPH_GLOW, rect.inflate(-8, -8), 1)
    pygame.draw.rect(surf, TITLE_INK, rect.inflate(-16, -16), 1)
    corner = 18
    for sx in (rect.left, rect.right):
        for sy in (rect.top, rect.bottom):
            dx = 1 if sx == rect.left else -1
            dy = 1 if sy == rect.top else -1
            pygame.draw.line(surf, border, (sx, sy + dy * corner), (sx + dx * corner, sy), 2)


# ============================================================================
# Post-processing helpers (bloom + vignette).
#
# Both helpers operate on the logical render surface so their cost scales
# with SCREEN_W x SCREEN_H, NOT with the actual window size. They look
# identical regardless of RENDER_SCALE because they run before the final
# upscale to the OS window.
# ============================================================================

def make_vignette(w: int, h: int,
                  *, strength: int = 170, falloff: float = 2.2) -> pygame.Surface:
    """Build a radial corner-darkening overlay (call once at startup).

    Internally we paint a tiny 96x96 alpha gradient and let smoothscale do
    the heavy lifting; per-pixel set_at on the full-size surface would be
    too slow on the web build.
    """
    small_n = 96
    g = pygame.Surface((small_n, small_n), pygame.SRCALPHA)
    cx = (small_n - 1) / 2.0
    cy = (small_n - 1) / 2.0
    max_d = math.hypot(cx, cy)
    for y in range(small_n):
        for x in range(small_n):
            d = math.hypot(x - cx, y - cy) / max_d
            a = int(min(255, max(0, (d ** falloff) * strength)))
            g.set_at((x, y), (0, 0, 0, a))
    return pygame.transform.smoothscale(g, (w, h))


def apply_bloom(frame: pygame.Surface, *,
                downsample: int = 4, blur_radius: int = 6,
                intensity: int = 70) -> None:
    """Add a soft bloom glow in-place on `frame`.

    Pipeline: downsample -> box-blur -> pre-multiply by intensity ->
    upscale -> additively composite back onto `frame`. Because the source
    is multiplied by intensity/255 before the additive blend, bright
    pixels (glyphs, charge, embers) gain a visible halo while dark pixels
    contribute almost nothing - that's the look we want.

    Cost is proportional to (frame_size / downsample**2). With the
    defaults below at 960x544 / down=4, the blurred buffer is 240x136
    which is essentially free on modern CPUs and on emscripten.
    """
    if intensity <= 0:
        return
    w, h = frame.get_size()
    sw = max(1, w // downsample)
    sh = max(1, h // downsample)
    small = pygame.transform.smoothscale(frame, (sw, sh))
    # box_blur was added in pygame-ce 2.4; available in pygbag 0.9.3.
    try:
        blurred = pygame.transform.box_blur(small, blur_radius)
    except (AttributeError, ValueError):
        # Cheap fallback: smoothscale-down then up to fake a blur.
        tiny = pygame.transform.smoothscale(small, (max(1, sw // 2), max(1, sh // 2)))
        blurred = pygame.transform.smoothscale(tiny, (sw, sh))
    # Pre-multiply the blur by `intensity / 255` so additive composition
    # adds at most `intensity` to any given channel.
    mul = pygame.Surface(blurred.get_size()).convert()
    mul.fill((intensity, intensity, intensity))
    blurred.blit(mul, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    up = pygame.transform.smoothscale(blurred, (w, h))
    frame.blit(up, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
