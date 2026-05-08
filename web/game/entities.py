"""Dynamic entities (mechanisms, enemies, pickups, projectiles) with richer art."""
from __future__ import annotations
import math
import random
import pygame

from .constants import TILE, SCREEN_W, SCREEN_H, GRID_ROWS
from . import render as R
from . import particles
from . import audio as A


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _world_to_screen(world_x: float, camera_x: float) -> int:
    return int(world_x - camera_x)


def _on_screen(world_x: float, camera_x: float, margin: int = 64) -> bool:
    sx = world_x - camera_x
    return -margin <= sx <= SCREEN_W + margin


def _circle_alpha(surf, color, center, radius, alpha):
    s = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, alpha), (radius + 2, radius + 2), radius)
    surf.blit(s, (center[0] - radius - 2, center[1] - radius - 2))


# ---------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------

class Entity:
    is_solid_to_player = False
    deals_damage_on_touch = False
    is_pickup = False
    is_enemy = False
    is_projectile = False

    def __init__(self) -> None:
        self.alive = True

    @property
    def rect(self) -> pygame.Rect:
        raise NotImplementedError

    def update(self, dt: float, world, em, player) -> None:
        pass

    def draw(self, surf: pygame.Surface, camera_x: float) -> None:
        pass

    def platform_top(self) -> int | None:
        return None


# ---------------------------------------------------------------------
# Pickups
# ---------------------------------------------------------------------

class GlyphPickup(Entity):
    is_pickup = True

    def __init__(self, world_x: float, world_y: float) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self._t = random.random() * 6.28

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 9, int(self.y) - 9, 18, 18)

    def update(self, dt, world, em, player) -> None:
        self._t += dt * 4
        if self.alive and self.rect.colliderect(player.rect):
            self.alive = False
            player.collect_glyph(1)
            A.get().play("glyph_pickup")
            ps = particles.get()
            ps.burst_sparks(self.x, self.y, color=R.GLYPH_GLOW_S, n=10, speed=180, life=0.4)

    def draw(self, surf, camera_x):
        sx = _world_to_screen(self.x, camera_x)
        sy = int(self.y + math.sin(self._t) * 3)
        # Outer halo.
        _circle_alpha(surf, R.GLYPH_GLOW, (sx, sy), 14, 50)
        _circle_alpha(surf, R.GLYPH_GLOW_S, (sx, sy), 10, 90)
        # Disc.
        pygame.draw.circle(surf, R.GLYPH_GLOW, (sx, sy), 8)
        pygame.draw.circle(surf, R.GLYPH_GLOW_S, (sx - 2, sy - 2), 3)
        pygame.draw.circle(surf, R.STONE_DARK, (sx, sy), 8, 1)
        # Cuneiform mark.
        pygame.draw.line(surf, R.STONE_DARK, (sx - 3, sy), (sx + 3, sy), 1)
        pygame.draw.line(surf, R.STONE_DARK, (sx, sy - 3), (sx, sy + 3), 1)


class HeartPickup(Entity):
    is_pickup = True

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self._t = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 10, int(self.y) - 9, 20, 18)

    def update(self, dt, world, em, player):
        self._t += dt * 5
        if self.alive and self.rect.colliderect(player.rect):
            self.alive = False
            player.heal(1)
            A.get().play("heart_pickup")
            ps = particles.get()
            ps.burst_sparks(self.x, self.y, color=R.HEART_RED, n=12, speed=180, life=0.5)

    def draw(self, surf, camera_x):
        sx = _world_to_screen(self.x, camera_x)
        sy = int(self.y + math.sin(self._t) * 2)
        _circle_alpha(surf, R.HEART_RED, (sx, sy), 14, 50)
        # Heart shape: two circles + diamond.
        pygame.draw.circle(surf, R.HEART_RED, (sx - 4, sy - 2), 6)
        pygame.draw.circle(surf, R.HEART_RED, (sx + 4, sy - 2), 6)
        pygame.draw.polygon(surf, R.HEART_RED,
                            [(sx - 9, sy - 1), (sx + 9, sy - 1), (sx, sy + 9)])
        # Highlight.
        pygame.draw.circle(surf, R.BONE, (sx - 5, sy - 4), 2)
        # Outline.
        pygame.draw.circle(surf, (130, 30, 40), (sx - 4, sy - 2), 6, 1)
        pygame.draw.circle(surf, (130, 30, 40), (sx + 4, sy - 2), 6, 1)


# ---------------------------------------------------------------------
# Hazards
# ---------------------------------------------------------------------

class MirrorBeam(Entity):
    deals_damage_on_touch = True
    LENGTH = 14 * TILE
    HEIGHT = 8

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self._t = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) + 16, int(self.y) - self.HEIGHT // 2,
                           self.LENGTH, self.HEIGHT)

    def update(self, dt, world, em, player):
        self._t += dt
        if self.alive and self.rect.colliderect(player.rect):
            player.take_hit(em)
        # Tiny beam motes.
        if random.random() < 0.5:
            ps = particles.get()
            x = self.x + 16 + random.uniform(0, self.LENGTH)
            ps.add(particles.Particle(
                x, self.y + random.uniform(-3, 3),
                random.uniform(-30, 30), random.uniform(-30, 30),
                life=0.3, color=R.GLYPH_GLOW_S, size=1.5,
            ))

    def draw(self, surf, camera_x):
        sx = _world_to_screen(self.x, camera_x)
        sy = int(self.y)
        # Emitter housing.
        pygame.draw.circle(surf, R.STONE_DARK, (sx, sy), 16)
        pygame.draw.circle(surf, R.LAPIS, (sx, sy), 14)
        pygame.draw.circle(surf, R.LAPIS_LIGHT, (sx, sy), 12)
        # Mirror disc with shine.
        pygame.draw.circle(surf, (200, 230, 255), (sx, sy), 10)
        pygame.draw.circle(surf, R.BONE, (sx - 3, sy - 3), 4)
        pygame.draw.circle(surf, R.STONE_DARK, (sx, sy), 14, 2)
        # Beam (multi-layer glow).
        beam_x = sx + 14
        # Outer halo.
        halo = pygame.Surface((self.LENGTH, 22), pygame.SRCALPHA)
        for i in range(11):
            a = max(0, 100 - i * 9)
            pygame.draw.rect(halo, (*R.EMBER, a), (0, 11 - i, self.LENGTH, i * 2))
        surf.blit(halo, (beam_x, sy - 11))
        # Bright core.
        pygame.draw.rect(surf, R.EMBER, (beam_x, sy - 3, self.LENGTH, 6))
        pygame.draw.rect(surf, R.GLYPH_GLOW_S, (beam_x, sy - 1, self.LENGTH, 2))
        # End burst.
        pulse = 4 + int(math.sin(self._t * 12) * 2)
        _circle_alpha(surf, R.EMBER, (beam_x + self.LENGTH, sy), pulse + 4, 100)
        pygame.draw.circle(surf, R.GLYPH_GLOW_S, (beam_x + self.LENGTH, sy), pulse)


class FirePiston(Entity):
    deals_damage_on_touch = True
    REACH = 6 * TILE
    THICK = 18

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self._t = random.random() * 2.0
        self.period = 2.4
        self.fire_time = 0.9

    @property
    def firing(self) -> bool:
        return (self._t % self.period) < self.fire_time

    @property
    def rect(self) -> pygame.Rect:
        if not self.firing:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(int(self.x) + 14, int(self.y) - self.THICK // 2,
                           self.REACH, self.THICK)

    def update(self, dt, world, em, player):
        was_firing = self.firing
        self._t += dt
        if self.firing:
            if self.rect.colliderect(player.rect):
                player.take_hit(em)
            # Emit a few fire particles per frame.
            ps = particles.get()
            for _ in range(2):
                fx = self.x + 16 + random.uniform(0, self.REACH * 0.95)
                ps.burst_fire(fx, self.y + random.uniform(-4, 4))

    def draw(self, surf, camera_x):
        sx = _world_to_screen(self.x, camera_x)
        sy = int(self.y)
        # Stone housing.
        pygame.draw.rect(surf, R.STONE_DARK, (sx - 10, sy - 16, 24, 32))
        pygame.draw.rect(surf, R.STONE, (sx - 8, sy - 14, 20, 28))
        # Bronze nozzle.
        pygame.draw.rect(surf, R.GEAR_BRONZE_D, (sx - 6, sy - 10, 18, 20))
        pygame.draw.rect(surf, R.COPPER, (sx - 4, sy - 8, 14, 16))
        pygame.draw.rect(surf, R.COPPER_LIGHT, (sx - 4, sy - 8, 14, 2))
        # Rivets.
        for ry in (-12, 12):
            pygame.draw.circle(surf, R.GEAR_BRONZE_D, (sx - 7, sy + ry), 2)
            pygame.draw.circle(surf, R.GEAR_BRONZE_D, (sx + 11, sy + ry), 2)
        # Flame.
        if self.firing:
            phase = (self._t % self.period) / self.fire_time
            tip_x = sx + 14 + int(self.REACH * min(1.0, phase * 1.4))
            length = max(0, tip_x - (sx + 14))
            # Outer glow.
            glow = pygame.Surface((length, self.THICK + 14), pygame.SRCALPHA)
            for i in range(8):
                a = max(0, 110 - i * 12)
                pygame.draw.rect(glow, (255, 80, 30, a),
                                 (0, (self.THICK + 14) // 2 - i * 2,
                                  length, i * 4))
            surf.blit(glow, (sx + 14, sy - (self.THICK + 14) // 2))
            # Body.
            pygame.draw.rect(surf, R.EMBER_DIM,
                             (sx + 14, sy - self.THICK // 2, length, self.THICK))
            pygame.draw.rect(surf, R.EMBER,
                             (sx + 14, sy - self.THICK // 2 + 3, length, self.THICK - 6))
            pygame.draw.rect(surf, R.GLYPH_GLOW_S,
                             (sx + 14, sy - 2, max(0, length - 8), 4))


class SteamJet(Entity):
    HEIGHT = 6 * TILE
    WIDTH  = 22

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self._t = random.random() * 2.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - self.WIDTH // 2, int(self.y) - self.HEIGHT,
                           self.WIDTH, self.HEIGHT)

    def update(self, dt, world, em, player):
        self._t += dt * 3
        if self.alive and self.rect.colliderect(player.rect):
            player.apply_steam_boost()
        # Continuous steam emission.
        ps = particles.get()
        for _ in range(2):
            ps.burst_steam(self.x, self.y - 4)

    def draw(self, surf, camera_x):
        sx = _world_to_screen(self.x, camera_x)
        sy = int(self.y)
        # Brass vent base.
        pygame.draw.rect(surf, R.STONE_DARK, (sx - 14, sy - 8, 28, 12))
        pygame.draw.rect(surf, R.GEAR_BRONZE_D, (sx - 12, sy - 6, 24, 10))
        pygame.draw.rect(surf, R.COPPER, (sx - 10, sy - 4, 20, 8))
        pygame.draw.line(surf, R.COPPER_LIGHT, (sx - 10, sy - 4), (sx + 10, sy - 4), 1)
        # Slot.
        pygame.draw.rect(surf, R.STONE_DARK, (sx - 8, sy - 2, 16, 3))
        # Side bolts.
        pygame.draw.circle(surf, R.GEAR_BRONZE_D, (sx - 10, sy + 2), 2)
        pygame.draw.circle(surf, R.GEAR_BRONZE_D, (sx + 10, sy + 2), 2)
        # Faint heat shimmer (rendered on top of particles).
        for i in range(4):
            yoff = i * (self.HEIGHT // 5)
            alpha = max(20, 70 - i * 15)
            haze = pygame.Surface((self.WIDTH + 6, 6), pygame.SRCALPHA)
            haze.fill((255, 200, 130, alpha))
            surf.blit(haze, (sx - self.WIDTH // 2 - 3, sy - yoff - 6))


# ---------------------------------------------------------------------
# Mechanisms (solid platforms)
# ---------------------------------------------------------------------

class GearPlatform(Entity):
    is_solid_to_player = True
    RADIUS = 38
    PAD_W  = 64

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.cx = world_x
        self.cy = world_y
        self.angle = random.random() * 6.28
        self.spin = random.choice([-1, 1]) * 1.2

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.cx) - self.PAD_W // 2, int(self.cy) - self.RADIUS,
                           self.PAD_W, 8)

    def platform_top(self) -> int:
        return int(self.cy) - self.RADIUS

    def update(self, dt, world, em, player):
        self.angle += self.spin * dt

    def draw(self, surf, camera_x):
        cx = _world_to_screen(self.cx, camera_x)
        cy = int(self.cy)
        R_ = self.RADIUS
        # Drop shadow.
        _circle_alpha(surf, (0, 0, 0), (cx + 3, cy + 4), R_ + 4, 60)
        # Outer ring (gear teeth).
        teeth_r = R_ + 6
        pygame.draw.circle(surf, R.GEAR_BRONZE_D, (cx, cy), teeth_r)
        # Teeth (rotating).
        for i in range(12):
            a = self.angle + i * (math.pi / 6)
            tx = cx + math.cos(a) * (teeth_r + 2)
            ty = cy + math.sin(a) * (teeth_r + 2)
            tooth = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.rect(tooth, R.GEAR_BRONZE_D, (0, 0, 10, 10))
            pygame.draw.rect(tooth, R.GEAR_BRONZE, (1, 1, 8, 8))
            surf.blit(tooth, (int(tx) - 5, int(ty) - 5))
        # Body.
        pygame.draw.circle(surf, R.GEAR_BRONZE, (cx, cy), R_)
        pygame.draw.circle(surf, R.COPPER_LIGHT, (cx - 6, cy - 8), R_ - 14)  # highlight
        pygame.draw.circle(surf, R.GEAR_BRONZE_D, (cx, cy), R_, 3)
        # Spokes (rotate).
        for i in range(6):
            a = self.angle + i * (math.pi / 3)
            ex = cx + math.cos(a) * (R_ - 6)
            ey = cy + math.sin(a) * (R_ - 6)
            pygame.draw.line(surf, R.STONE_DARK, (cx, cy), (int(ex), int(ey)), 3)
            pygame.draw.line(surf, R.GEAR_BRONZE_D, (cx, cy), (int(ex), int(ey)), 1)
        # Hub.
        pygame.draw.circle(surf, R.STONE_DARK, (cx, cy), 10)
        pygame.draw.circle(surf, R.COPPER, (cx, cy), 6)
        pygame.draw.circle(surf, R.GLYPH_GLOW_S, (cx - 1, cy - 1), 2)
        # Standable plank highlight on the rim.
        pad = self.rect
        pad_screen = pygame.Rect(pad.x - int(camera_x), pad.y, pad.w, pad.h)
        pygame.draw.rect(surf, R.COPPER_LIGHT, pad_screen)
        pygame.draw.rect(surf, R.STONE_DARK, pad_screen, 1)
        # Top rim shine.
        pygame.draw.line(surf, R.GLYPH_GLOW_S,
                         (pad_screen.left + 4, pad_screen.top + 1),
                         (pad_screen.right - 5, pad_screen.top + 1), 1)


class CatapultPad(Entity):
    is_solid_to_player = True
    WIDTH  = TILE
    HEIGHT = 14

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self._cooldown = 0.0
        self._squish = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y) - self.HEIGHT,
                           self.WIDTH, self.HEIGHT)

    def platform_top(self) -> int:
        return int(self.y) - self.HEIGHT

    def update(self, dt, world, em, player):
        self._cooldown = max(0.0, self._cooldown - dt)
        self._squish = max(0.0, self._squish - dt * 4)
        pr = player.rect
        if (self._cooldown <= 0
                and pr.bottom >= self.rect.top - 1
                and pr.bottom <= self.rect.top + 4
                and pr.right > self.rect.left
                and pr.left < self.rect.right
                and player.vy >= 0):
            self._cooldown = 0.7
            self._squish = 1.0
            player.launch(vx_boost=320.0, vy=-820.0)
            ps = particles.get()
            ps.burst_sparks(self.x + self.WIDTH / 2, self.y - 4,
                            color=R.GLYPH_GLOW, n=12, speed=240, life=0.4)
            ps.burst_dust(self.x + self.WIDTH / 2, self.y - 2, n=8)

    def draw(self, surf, camera_x):
        rx = _world_to_screen(self.x, camera_x)
        ry = int(self.y) - self.HEIGHT
        sq = int(self._squish * 6)
        # Base.
        pygame.draw.rect(surf, R.STONE_DARK, (rx - 4, ry + 8, self.WIDTH + 8, 8))
        pygame.draw.rect(surf, R.STONE, (rx - 2, ry + 9, self.WIDTH + 4, 6))
        # Spring (zigzag).
        for i in range(3):
            y0 = ry + 8 - i * 2
            x0 = rx + 4 + (i % 2) * 6
            pygame.draw.line(surf, R.GEAR_BRONZE_D,
                             (rx + 4, y0), (rx + self.WIDTH - 4, y0 - 1), 2)
        # Plate (squishes).
        pygame.draw.rect(surf, R.COPPER_LIGHT, (rx, ry + sq, self.WIDTH, 8 - sq // 2))
        pygame.draw.rect(surf, R.COPPER, (rx, ry + sq + 2, self.WIDTH, 4 - sq // 2))
        pygame.draw.rect(surf, R.GEAR_BRONZE_D, (rx, ry + sq, self.WIDTH, 8 - sq // 2), 1)
        # Rivets on plate.
        for px in (rx + 4, rx + self.WIDTH - 5):
            pygame.draw.circle(surf, R.GEAR_BRONZE_D, (px, ry + sq + 2), 2)
            pygame.draw.circle(surf, R.GLYPH_GLOW, (px - 1, ry + sq + 1), 1)


# ---------------------------------------------------------------------
# Projectiles
# ---------------------------------------------------------------------

class CannonBolt(Entity):
    is_projectile = True
    deals_damage_on_touch = True
    SPEED = 260.0
    LIFE  = 5.0

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self._life = self.LIFE
        self._t = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 8, int(self.y) - 5, 18, 10)

    def update(self, dt, world, em, player):
        self.x -= self.SPEED * dt
        self._life -= dt
        self._t += dt
        # Smoke trail.
        ps = particles.get()
        ps.add(particles.Particle(
            self.x + 6, self.y, random.uniform(20, 50), random.uniform(-15, 15),
            life=0.4, color=(80, 60, 50), size=3, drag=2.0,
        ))
        if self._life <= 0:
            self.alive = False; return
        if world.overlaps_solid(self.rect):
            self.alive = False
            ps.burst_sparks(self.x, self.y, color=R.GLYPH_GLOW, n=10, speed=200, life=0.3)
            return
        if self.rect.colliderect(player.rect):
            player.take_hit(em)
            self.alive = False

    def draw(self, surf, camera_x):
        sx = _world_to_screen(self.x, camera_x)
        sy = int(self.y)
        # Glow.
        _circle_alpha(surf, R.EMBER, (sx, sy), 9, 90)
        # Body (cannonball with banded ring).
        pygame.draw.circle(surf, R.STONE_DARK, (sx, sy), 6)
        pygame.draw.circle(surf, R.STONE, (sx - 1, sy - 1), 5)
        pygame.draw.circle(surf, R.STONE_LIGHT, (sx - 2, sy - 2), 2)
        pygame.draw.circle(surf, R.GEAR_BRONZE_D, (sx, sy), 6, 1)
        # Sparking fuse.
        if int(self._t * 20) % 2 == 0:
            pygame.draw.circle(surf, R.GLYPH_GLOW_S, (sx + 6, sy), 2)


class Cannon(Entity):
    PERIOD = 2.2

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self._t = random.random() * self.PERIOD
        self._recoil = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 18, int(self.y) - 14, 32, 28)

    def update(self, dt, world, em, player):
        self._t += dt
        self._recoil = max(0.0, self._recoil - dt * 5)
        if self._t >= self.PERIOD:
            self._t = 0
            if _on_screen(self.x, world.camera_x, margin=200):
                em.add(CannonBolt(self.x - 14, self.y))
                self._recoil = 1.0
                ps = particles.get()
                # Muzzle flash.
                ps.burst_sparks(self.x - 18, self.y, color=R.GLYPH_GLOW_S,
                                n=10, speed=260, life=0.25)
                # Smoke puff.
                for _ in range(6):
                    ps.add(particles.Particle(
                        self.x - 18, self.y + random.uniform(-3, 3),
                        random.uniform(-100, -30), random.uniform(-40, 20),
                        life=0.6, color=(180, 170, 150), size=5, drag=2.0,
                    ))

    def draw(self, surf, camera_x):
        sx = _world_to_screen(self.x, camera_x)
        sy = int(self.y)
        recoil = int(self._recoil * 5)
        # Carriage.
        pygame.draw.rect(surf, R.STONE_DARK, (sx - 12, sy + 4, 30, 12))
        pygame.draw.rect(surf, R.STONE, (sx - 10, sy + 6, 26, 8))
        # Wheels.
        for wx in (sx - 6, sx + 14):
            pygame.draw.circle(surf, R.STONE_DARK, (wx, sy + 16), 5)
            pygame.draw.circle(surf, R.GEAR_BRONZE_D, (wx, sy + 16), 4)
            pygame.draw.line(surf, R.STONE_DARK, (wx - 3, sy + 16), (wx + 3, sy + 16), 1)
            pygame.draw.line(surf, R.STONE_DARK, (wx, sy + 13), (wx, sy + 19), 1)
        # Barrel pointing left.
        bx = sx - 16 + recoil
        pygame.draw.rect(surf, R.GEAR_BRONZE_D, (bx, sy - 6, 26, 12))
        pygame.draw.rect(surf, R.COPPER, (bx, sy - 4, 24, 8))
        pygame.draw.rect(surf, R.COPPER_LIGHT, (bx, sy - 4, 24, 2))
        # Bands.
        pygame.draw.line(surf, R.GEAR_BRONZE_D, (bx + 6, sy - 6), (bx + 6, sy + 6), 1)
        pygame.draw.line(surf, R.GEAR_BRONZE_D, (bx + 18, sy - 6), (bx + 18, sy + 6), 1)
        # Muzzle.
        pygame.draw.circle(surf, R.STONE_DARK, (bx, sy), 5)
        pygame.draw.circle(surf, (10, 10, 10), (bx, sy), 3)


class GlyphBomb(Entity):
    is_projectile = True
    LIFE = 1.6

    def __init__(self, world_x, world_y, vx, vy) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self.vx = vx
        self.vy = vy
        self._life = self.LIFE
        self._t = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 7, int(self.y) - 7, 14, 14)

    def _explode(self, world, em):
        self.alive = False
        A.get().play("explode")
        em.add(Explosion(self.x, self.y))
        particles.get().burst_explosion(self.x, self.y)
        for e in em.entities:
            if e.is_enemy and e.alive:
                er = e.rect
                dx = er.centerx - self.x
                dy = er.centery - self.y
                if dx * dx + dy * dy <= 48 * 48:
                    e.take_damage(2)

    def update(self, dt, world, em, player):
        self._life -= dt
        self._t += dt * 12
        self.vy += 1400.0 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        # Sparkle trail.
        if random.random() < 0.6:
            particles.get().add(particles.Particle(
                self.x, self.y, random.uniform(-30, 30), random.uniform(-30, 30),
                life=0.3, color=R.GLYPH_GLOW_S, size=2, drag=3.0,
            ))
        if self._life <= 0:
            self._explode(world, em); return
        if world.overlaps_solid(self.rect):
            self._explode(world, em); return

    def draw(self, surf, camera_x):
        sx = _world_to_screen(self.x, camera_x)
        sy = int(self.y)
        # Pulsing glow.
        pulse = 6 + int((math.sin(self._t) + 1) * 2)
        _circle_alpha(surf, R.GLYPH_GLOW, (sx, sy), pulse + 4, 100)
        pygame.draw.circle(surf, R.STONE_DARK, (sx, sy), 7)
        pygame.draw.circle(surf, R.GLYPH_GLOW, (sx, sy), 5)
        pygame.draw.circle(surf, R.GLYPH_GLOW_S, (sx - 1, sy - 1), 2)
        # Glyph mark.
        pygame.draw.line(surf, R.STONE_DARK, (sx - 2, sy), (sx + 2, sy), 1)
        pygame.draw.line(surf, R.STONE_DARK, (sx, sy - 2), (sx, sy + 2), 1)


class Explosion(Entity):
    LIFE = 0.4

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.x = world_x
        self.y = world_y
        self._life = self.LIFE

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 28, int(self.y) - 28, 56, 56)

    def update(self, dt, world, em, player):
        self._life -= dt
        if self._life <= 0:
            self.alive = False

    def draw(self, surf, camera_x):
        t = 1.0 - max(0.0, self._life / self.LIFE)
        radius = int(10 + 30 * t)
        sx = _world_to_screen(self.x, camera_x)
        sy = int(self.y)
        # Outer ring.
        ring_alpha = max(0, int(180 * (1 - t)))
        _circle_alpha(surf, R.EMBER, (sx, sy), radius + 4, max(40, ring_alpha // 2))
        # Body.
        _circle_alpha(surf, R.EMBER, (sx, sy), radius, ring_alpha)
        # Bright core.
        core_r = max(2, radius - 8)
        _circle_alpha(surf, R.GLYPH_GLOW_S, (sx, sy), core_r, max(0, int(200 * (1 - t))))


# ---------------------------------------------------------------------
# Enemies
# ---------------------------------------------------------------------

class Automaton(Entity):
    is_enemy = True
    deals_damage_on_touch = True
    WIDTH  = 24
    HEIGHT = 30
    SPEED  = 60.0
    HP     = 2

    def __init__(self, world_x, world_y) -> None:
        super().__init__()
        self.x = world_x
        self.surface_y = world_y
        self.dir = -1
        self.hp = self.HP
        self._hurt = 0.0
        self._t = 0.0

    @property
    def y(self) -> float:
        return self.surface_y - self.HEIGHT

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.WIDTH, self.HEIGHT)

    def take_damage(self, dmg: int) -> None:
        if not self.alive:
            return
        self.hp -= dmg
        self._hurt = 0.12
        ps = particles.get()
        ps.burst_sparks(self.rect.centerx, self.rect.centery,
                        color=R.GLYPH_GLOW, n=8, speed=200, life=0.3)
        if self.hp <= 0:
            self.alive = False
            # Death debris.
            for _ in range(14):
                ang = random.uniform(0, math.tau)
                spd = random.uniform(80, 220)
                ps.add(particles.Particle(
                    self.rect.centerx, self.rect.centery,
                    math.cos(ang) * spd, math.sin(ang) * spd - 40,
                    life=random.uniform(0.5, 0.9),
                    color=random.choice([R.GEAR_BRONZE, R.GEAR_BRONZE_D, R.STONE_DARK]),
                    size=random.uniform(2, 4), gravity=600, drag=1.5,
                ))

    def update(self, dt, world, em, player):
        self._t += dt
        self._hurt = max(0.0, self._hurt - dt)
        nx = self.x + self.dir * self.SPEED * dt
        probe_x = nx + (self.WIDTH if self.dir > 0 else 0)
        floor_below = world.is_solid(probe_x, self.surface_y + 4)
        wall_ahead = world.is_solid(probe_x + (2 if self.dir > 0 else -2),
                                    self.surface_y - self.HEIGHT // 2)
        if not floor_below or wall_ahead:
            self.dir *= -1
        else:
            self.x = nx
        if self.alive and self.rect.colliderect(player.rect):
            if player.is_dashing:
                self.take_damage(2)
            elif player.vy > 80 and player.rect.bottom - 6 <= self.rect.top + 6:
                self.take_damage(2)
                player.bounce()
            else:
                player.take_hit(em)
        if self.x < world.camera_x - SCREEN_W:
            self.alive = False

    def draw(self, surf, camera_x):
        rx = _world_to_screen(self.x, camera_x)
        ry = int(self.y)
        body_color = R.BLOOD if self._hurt > 0 else R.GEAR_BRONZE
        body_dark  = R.GEAR_BRONZE_D
        # Drop shadow.
        _circle_alpha(surf, (0, 0, 0), (rx + self.WIDTH // 2, int(self.surface_y) + 2),
                      self.WIDTH // 2 + 2, 70)
        # Torso.
        torso = pygame.Rect(rx, ry + 6, self.WIDTH, self.HEIGHT - 6)
        pygame.draw.rect(surf, body_color, torso)
        pygame.draw.rect(surf, body_dark, torso, 2)
        # Plate highlight.
        pygame.draw.line(surf, R.COPPER_LIGHT, (rx + 1, ry + 7), (rx + self.WIDTH - 2, ry + 7), 1)
        # Rivets.
        for ry_off in (10, 20):
            pygame.draw.circle(surf, body_dark, (rx + 4, ry + ry_off), 2)
            pygame.draw.circle(surf, body_dark, (rx + self.WIDTH - 5, ry + ry_off), 2)
        # Chest gear.
        cx, cy = rx + self.WIDTH // 2, ry + 16
        pygame.draw.circle(surf, body_dark, (cx, cy), 5)
        pygame.draw.circle(surf, R.COPPER, (cx, cy), 3)
        for i in range(4):
            a = self._t * 3 + i * (math.pi / 2)
            ex = cx + int(math.cos(a) * 5); ey = cy + int(math.sin(a) * 5)
            pygame.draw.line(surf, body_dark, (cx, cy), (ex, ey), 1)
        # Head dome.
        head_cx = rx + self.WIDTH // 2
        head_cy = ry + 2
        pygame.draw.circle(surf, body_color, (head_cx, head_cy), 8)
        pygame.draw.circle(surf, body_dark, (head_cx, head_cy), 8, 2)
        # Eye slot (glowing).
        eye_x = head_cx + (3 if self.dir > 0 else -3)
        pygame.draw.rect(surf, R.STONE_DARK, (head_cx - 5, head_cy - 1, 10, 3))
        _circle_alpha(surf, R.EMBER, (eye_x, head_cy), 4, 160)
        pygame.draw.circle(surf, R.GLYPH_GLOW_S, (eye_x, head_cy), 1)
        # Antenna.
        pygame.draw.line(surf, body_dark, (head_cx, head_cy - 8),
                         (head_cx + (1 if self.dir > 0 else -1), head_cy - 12), 1)
        pygame.draw.circle(surf, R.EMBER, (head_cx + (1 if self.dir > 0 else -1), head_cy - 13), 1)
        # Walking legs.
        leg_off = int(math.sin(self._t * 10) * 3)
        # Left leg.
        pygame.draw.rect(surf, body_dark, (rx + 3, ry + self.HEIGHT - 2, 6, 3 + leg_off))
        # Right leg.
        pygame.draw.rect(surf, body_dark, (rx + self.WIDTH - 9, ry + self.HEIGHT - 2,
                                           6, 3 - leg_off))
        # HP pip bar.
        if self.hp < self.HP:
            for i in range(self.hp):
                pygame.draw.rect(surf, R.CHARGE_FULL, (rx + 2 + i * 6, ry - 14, 4, 3))
                pygame.draw.rect(surf, R.STONE_DARK, (rx + 2 + i * 6, ry - 14, 4, 3), 1)


# ---------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------

class EntityManager:
    def __init__(self) -> None:
        self.entities: list[Entity] = []

    def reset(self) -> None:
        self.entities.clear()

    def add(self, e: Entity) -> None:
        self.entities.append(e)

    def spawn_from_spec(self, spec, chunk_x_off: int) -> None:
        wx = chunk_x_off + spec.col * TILE + TILE // 2
        if spec.kind == "glyph":
            self.add(GlyphPickup(wx, spec.row * TILE + TILE // 2))
        elif spec.kind == "heart":
            self.add(HeartPickup(wx, spec.row * TILE + TILE // 2))
        elif spec.kind == "automaton":
            surface_y = self._floor_below(chunk_x_off, spec)
            self.add(Automaton(wx, surface_y))
        elif spec.kind == "catapult":
            surface_y = self._floor_below(chunk_x_off, spec)
            self.add(CatapultPad(wx - TILE // 2, surface_y))
        elif spec.kind == "steam":
            surface_y = self._floor_below(chunk_x_off, spec)
            self.add(SteamJet(wx, surface_y))
        elif spec.kind == "gear":
            self.add(GearPlatform(wx, spec.row * TILE + TILE // 2))
        elif spec.kind == "mirror":
            self.add(MirrorBeam(wx, spec.row * TILE + TILE // 2))
        elif spec.kind == "cannon":
            self.add(Cannon(wx, spec.row * TILE + TILE // 2))
        elif spec.kind == "firepiston":
            self.add(FirePiston(wx, spec.row * TILE + TILE // 2))

    def _floor_below(self, chunk_x_off: int, spec) -> int:
        return 14 * TILE

    def update_all(self, dt, world, player) -> None:
        for e in self.entities:
            if e.alive:
                e.update(dt, world, self, player)
        self.entities = [e for e in self.entities if e.alive]
        cull = world.camera_x - SCREEN_W
        self.entities = [e for e in self.entities
                         if not hasattr(e, 'x') or e.rect.right > cull]

    def draw_all(self, surf, camera_x) -> None:
        for e in self.entities:
            if e.alive and _on_screen(e.rect.centerx, camera_x, margin=80):
                e.draw(surf, camera_x)

    def solid_platforms(self):
        return [e for e in self.entities if e.alive and e.is_solid_to_player]
