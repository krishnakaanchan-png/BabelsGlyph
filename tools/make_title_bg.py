"""Generate the cinematic title-screen background asset."""
from __future__ import annotations

import math
import os
import random
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame


ROOT = Path(__file__).resolve().parents[1]
OUT_PATHS = [
    ROOT / "assets" / "title_bg.png",
    ROOT / "desktop" / "assets" / "title_bg.png",
    ROOT / "web" / "assets" / "title_bg.png",
]
W, H = 1920, 1088


def lerp(a, b, t):
    return int(a + (b - a) * t)


def lerp_color(a, b, t):
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t))


def glow_circle(surf, center, color, radius, alpha):
    layer = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -8):
        t = r / radius
        pygame.draw.circle(layer, (*color, int(alpha * (1.0 - t) ** 1.4)), (radius, radius), r)
    surf.blit(layer, (center[0] - radius, center[1] - radius), special_flags=pygame.BLEND_RGBA_ADD)


def draw_cloud(surf, rng, x, y, scale, color, shadow):
    count = rng.randint(5, 9)
    for i in range(count):
        cx = int(x + (i - count / 2) * 48 * scale + rng.randint(-18, 18) * scale)
        cy = int(y + rng.randint(-12, 12) * scale)
        rx = int(rng.randint(52, 112) * scale)
        ry = int(rng.randint(16, 36) * scale)
        pygame.draw.ellipse(surf, (*shadow, 74), (cx - rx, cy - ry + 14, rx * 2, ry * 2))
        pygame.draw.ellipse(surf, (*color, 120), (cx - rx, cy - ry, rx * 2, ry * 2))


def draw_ruin_block(surf, rng, x, base_y, w, h, depth=0):
    shade = max(0, min(255, 90 + depth * 22))
    base = (shade + 34, max(52, shade - 8), 32)
    edge = (48, 28, 20)
    lit = (226, 126, 45)
    rect = pygame.Rect(x, base_y - h, w, h)
    pygame.draw.rect(surf, base, rect)
    pygame.draw.rect(surf, edge, rect, max(2, W // 960))
    pygame.draw.line(surf, lit, rect.topleft, rect.topright, max(1, W // 960))
    for yy in range(rect.top + 18, rect.bottom, 42):
        pygame.draw.line(surf, (78, 44, 28), (rect.left, yy), (rect.right, yy), 2)
    for xx in range(rect.left + rng.randint(12, 34), rect.right, rng.randint(54, 86)):
        pygame.draw.line(surf, (62, 35, 24), (xx, rect.top), (xx + rng.randint(-10, 10), rect.bottom), 1)
    for _ in range(max(2, w // 70)):
        wx = rng.randint(rect.left + 8, rect.right - 24)
        wy = rng.randint(rect.top + 12, rect.bottom - 28)
        pygame.draw.rect(surf, (34, 22, 17), (wx, wy, rng.randint(10, 28), rng.randint(14, 36)))


def draw_ziggurat(surf, cx, base_y, steps, step_w, step_h, color, rim):
    for i in range(steps):
        width = (steps - i) * step_w
        rect = pygame.Rect(cx - width // 2, base_y - (i + 1) * step_h, width, step_h + 1)
        pygame.draw.rect(surf, color, rect)
        pygame.draw.line(surf, rim, rect.topleft, rect.topright, 2)
    pygame.draw.polygon(
        surf,
        rim,
        [(cx - step_w // 2, base_y - steps * step_h), (cx + step_w // 2, base_y - steps * step_h), (cx, base_y - (steps + 1) * step_h)],
    )


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    rng = random.Random(2417)
    surf = pygame.Surface((W, H)).convert()

    for y in range(H):
        t = y / H
        if t < 0.45:
            c = lerp_color((15, 12, 26), (92, 40, 34), t / 0.45)
        elif t < 0.72:
            c = lerp_color((92, 40, 34), (245, 122, 30), (t - 0.45) / 0.27)
        else:
            c = lerp_color((245, 122, 30), (56, 31, 23), (t - 0.72) / 0.28)
        pygame.draw.line(surf, c, (0, y), (W, y))

    horizon = int(H * 0.69)
    glow_circle(surf, (W // 2, horizon), (255, 190, 56), 440, 220)
    glow_circle(surf, (W // 2, horizon + 40), (255, 236, 150), 210, 170)

    stars = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(1450):
        x = rng.randrange(W)
        y = rng.randrange(0, int(H * 0.56))
        a = rng.randint(60, 220)
        r = 1 if rng.random() < 0.92 else 2
        col = rng.choice([(255, 232, 178), (255, 250, 224), (255, 190, 100)])
        pygame.draw.circle(stars, (*col, a), (x, y), r)
        if r == 2 and rng.random() < 0.35:
            pygame.draw.line(stars, (*col, a // 2), (x - 5, y), (x + 5, y), 1)
            pygame.draw.line(stars, (*col, a // 2), (x, y - 5), (x, y + 5), 1)
    surf.blit(stars, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    cloud_layer = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(15):
        draw_cloud(
            cloud_layer,
            rng,
            rng.randint(-120, W + 120),
            rng.randint(110, 470),
            rng.uniform(0.85, 1.9),
            (201, 91, 34),
            (78, 34, 24),
        )
    surf.blit(cloud_layer, (0, 0))

    far = pygame.Surface((W, H), pygame.SRCALPHA)
    for x in range(-80, W + 180, 170):
        h = rng.randint(140, 300)
        w = rng.randint(120, 250)
        draw_ruin_block(far, rng, x, horizon + rng.randint(40, 90), w, h, depth=0)
    draw_ziggurat(far, W // 2, horizon + 74, 8, 96, 32, (92, 48, 30), (214, 117, 40))
    surf.blit(far, (0, 0))

    mid = pygame.Surface((W, H), pygame.SRCALPHA)
    for x in range(-60, W + 220, 220):
        h = rng.randint(120, 340)
        w = rng.randint(150, 320)
        base = rng.randint(int(H * 0.72), int(H * 0.9))
        draw_ruin_block(mid, rng, x, base, w, h, depth=1)
    draw_ziggurat(mid, 290, int(H * 0.88), 6, 104, 34, (76, 42, 28), (198, 104, 39))
    draw_ziggurat(mid, W - 300, int(H * 0.86), 7, 100, 32, (72, 39, 28), (190, 98, 36))
    surf.blit(mid, (0, 0))

    fg = pygame.Surface((W, H), pygame.SRCALPHA)
    for x in range(-100, W + 180, 160):
        h = rng.randint(90, 250)
        w = rng.randint(120, 240)
        base = rng.randint(int(H * 0.85), H + 40)
        draw_ruin_block(fg, rng, x, base, w, h, depth=-1)
    for x in range(0, W, 38):
        pygame.draw.polygon(fg, (42, 25, 18, 220), [(x, H - 92), (x + 18, H - 178 + rng.randint(-24, 28)), (x + 36, H - 92)])
        pygame.draw.line(fg, (198, 96, 38, 140), (x + 18, H - 176), (x + 18, H - 104), 1)
    surf.blit(fg, (0, 0))

    dust = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(1900):
        x = rng.randrange(W)
        y = rng.randrange(int(H * 0.28), H)
        a = rng.randint(18, 95)
        r = rng.choice([1, 1, 1, 2])
        pygame.draw.circle(dust, (255, rng.randint(146, 215), 72, a), (x, y), r)
    surf.blit(dust, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(H):
        d = abs(y - H * 0.52) / (H * 0.52)
        a = int(max(0, (d ** 1.6) * 105))
        pygame.draw.line(shade, (0, 0, 0, a), (0, y), (W, y))
    for x in range(W):
        d = abs(x - W * 0.5) / (W * 0.5)
        a = int(max(0, (d ** 2.2) * 120))
        pygame.draw.line(shade, (0, 0, 0, a), (x, 0), (x, H))
    surf.blit(shade, (0, 0))

    for out_path in OUT_PATHS:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(surf, str(out_path))
        print(out_path)


if __name__ == "__main__":
    main()