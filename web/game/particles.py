"""Lightweight particle system — pure pygame primitives, no external deps."""
from __future__ import annotations
import math
import random
import pygame


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size",
                 "color", "gravity", "drag", "shrink", "kind")

    def __init__(self, x, y, vx, vy, life, color, *,
                 size=3.0, gravity=0.0, drag=0.0, shrink=True, kind="circle"):
        self.x = float(x); self.y = float(y)
        self.vx = float(vx); self.vy = float(vy)
        self.life = float(life); self.max_life = float(life)
        self.color = color
        self.size = float(size)
        self.gravity = float(gravity)
        self.drag = float(drag)
        self.shrink = bool(shrink)
        self.kind = kind  # "circle" or "square" or "spark"

    @property
    def alive(self) -> bool:
        return self.life > 0

    def update(self, dt: float) -> None:
        if self.life <= 0:
            return
        self.life -= dt
        self.vy += self.gravity * dt
        if self.drag:
            f = max(0.0, 1.0 - self.drag * dt)
            self.vx *= f; self.vy *= f
        self.x += self.vx * dt
        self.y += self.vy * dt


class ParticleSystem:
    def __init__(self) -> None:
        self.parts: list[Particle] = []

    def reset(self) -> None:
        self.parts.clear()

    def add(self, p: Particle) -> None:
        self.parts.append(p)

    # ------------------------------------------------------------------
    # Convenience emitters.
    def burst_dust(self, x, y, n=6, palette=((220,200,160), (200,170,120))):
        for _ in range(n):
            ang = random.uniform(-math.pi, 0)  # mostly upward / sideways
            spd = random.uniform(40, 110)
            self.add(Particle(
                x + random.uniform(-3, 3), y,
                math.cos(ang) * spd, math.sin(ang) * spd * 0.5 - 30,
                life=random.uniform(0.25, 0.45),
                color=random.choice(palette),
                size=random.uniform(2.5, 4.0),
                gravity=400, drag=2.0,
            ))

    def burst_landing(self, x, y, intensity=1.0):
        n = int(8 * intensity)
        for i in range(n):
            side = -1 if i < n // 2 else 1
            ang = math.pi + side * random.uniform(0.05, 0.5)
            spd = random.uniform(60, 160) * intensity
            self.add(Particle(
                x + random.uniform(-6, 6), y - 1,
                math.cos(ang) * spd, math.sin(ang) * spd - 60,
                life=random.uniform(0.3, 0.55),
                color=(220, 200, 160) if random.random() > 0.4 else (170, 140, 100),
                size=random.uniform(2.5, 4.5),
                gravity=520, drag=2.4,
            ))

    def burst_sparks(self, x, y, color=(255, 220, 130), n=10, speed=240, life=0.35):
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(speed * 0.4, speed)
            self.add(Particle(
                x, y,
                math.cos(ang) * spd, math.sin(ang) * spd,
                life=random.uniform(life * 0.6, life),
                color=color,
                size=random.uniform(1.5, 2.5),
                gravity=200, drag=2.0,
                kind="spark",
            ))

    def burst_explosion(self, x, y):
        # Bright core sparks.
        self.burst_sparks(x, y, color=(255, 245, 200), n=14, speed=320, life=0.45)
        # Orange smoke.
        for _ in range(14):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(40, 140)
            self.add(Particle(
                x, y,
                math.cos(ang) * spd, math.sin(ang) * spd - 30,
                life=random.uniform(0.5, 0.9),
                color=random.choice([(255, 122, 43), (200, 80, 40), (140, 60, 30)]),
                size=random.uniform(4, 8),
                gravity=-60, drag=2.5,
            ))

    def burst_fire(self, x, y):
        for _ in range(2):
            ang = random.uniform(-math.pi * 0.6, -math.pi * 0.4)
            spd = random.uniform(40, 120)
            self.add(Particle(
                x + random.uniform(-2, 2), y,
                math.cos(ang) * spd, math.sin(ang) * spd,
                life=random.uniform(0.25, 0.55),
                color=random.choice([(255, 210, 110), (255, 140, 60), (200, 80, 40)]),
                size=random.uniform(2, 4),
                gravity=-180, drag=1.5,
            ))

    def burst_steam(self, x, y):
        ang = -math.pi / 2 + random.uniform(-0.2, 0.2)
        spd = random.uniform(40, 80)
        self.add(Particle(
            x + random.uniform(-4, 4), y,
            math.cos(ang) * spd, math.sin(ang) * spd,
            life=random.uniform(0.7, 1.1),
            color=(240, 240, 240),
            size=random.uniform(5, 9),
            gravity=-40, drag=1.0,
        ))

    def trail_dash(self, x, y):
        for _ in range(2):
            self.add(Particle(
                x + random.uniform(-4, 4), y + random.uniform(-2, 2),
                random.uniform(-30, 30), random.uniform(-20, 10),
                life=random.uniform(0.18, 0.32),
                color=(255, 220, 150),
                size=random.uniform(2.5, 4.0),
                drag=4.0,
            ))

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        for p in self.parts:
            p.update(dt)
        if len(self.parts) > 800:
            # Drop oldest particles to bound the system.
            self.parts = [p for p in self.parts if p.alive][-800:]
        else:
            self.parts = [p for p in self.parts if p.alive]

    def draw(self, surf: pygame.Surface, camera_x: float) -> None:
        for p in self.parts:
            sx = int(p.x - camera_x)
            sy = int(p.y)
            if sx < -16 or sx > surf.get_width() + 16:
                continue
            t = max(0.0, min(1.0, p.life / p.max_life))
            sz = p.size * (t if p.shrink else 1.0)
            if sz < 0.6:
                continue
            alpha = int(255 * (0.5 + 0.5 * t))
            r = max(1, int(sz))
            if p.kind == "spark":
                # Bright streak in the velocity direction.
                ex = sx - int(p.vx * 0.02)
                ey = sy - int(p.vy * 0.02)
                pygame.draw.line(surf, p.color, (sx, sy), (ex, ey), 2)
            else:
                if alpha >= 250:
                    pygame.draw.circle(surf, p.color, (sx, sy), r)
                else:
                    s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*p.color, alpha), (r + 1, r + 1), r)
                    surf.blit(s, (sx - r - 1, sy - r - 1))


# Module-level singleton for convenience (set by Game on init).
PS: ParticleSystem | None = None


def get() -> ParticleSystem:
    global PS
    if PS is None:
        PS = ParticleSystem()
    return PS


def reset() -> None:
    get().reset()
