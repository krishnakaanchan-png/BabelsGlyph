"""Tile world: streams chunks from right, exposes tile/collision queries.

Visual upgrade:
- Tile sprites are pre-rendered into a cache (one per (tile, zone, variant))
  rather than redrawn from primitives every frame.
- Backgrounds use multiple parallax layers: sky gradient, sun/moon disc,
  drifting clouds, far mountain silhouettes, and stepped-ziggurat midground.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math
import random

import pygame

from .constants import (
    TILE, SCREEN_W, SCREEN_H, GRID_ROWS,
    T_AIR, T_STONE, T_BRICK, T_SPIKE, T_CRUMBLE, T_ONEWAY, T_FORGE, T_DECO,
    SOLID_TILES, ONEWAY_TILES, HAZARD_TILES,
    SCROLL_BASE, SCROLL_MAX, SCROLL_RAMP, ZONE_THRESHOLDS,
)
from . import render as R


# ============================================================================
# Tile sprite cache
# ============================================================================

_TILE_CACHE: dict[tuple[int, int, int], pygame.Surface] = {}


def _shade(color, factor):
    return (max(0, min(255, int(color[0] * factor))),
            max(0, min(255, int(color[1] * factor))),
            max(0, min(255, int(color[2] * factor))))


def _stone_block(zone: int, variant: int) -> pygame.Surface:
    """A chiseled stone block with bevel + carved seam + speckle noise."""
    s = pygame.Surface((TILE, TILE)).convert()
    if zone == 0:
        base = R.SANDSTONE
        edge = R.SANDSTONE_D
        light = R.SAND_LIGHT
    elif zone == 1:
        base = R.COPPER_LIGHT
        edge = R.COPPER
        light = (240, 190, 130)
    else:
        base = R.PARCHMENT
        edge = R.STONE_DARK
        light = (244, 230, 200)

    s.fill(base)
    # Top bevel highlight.
    pygame.draw.line(s, light, (0, 0), (TILE - 1, 0), 1)
    pygame.draw.line(s, light, (0, 0), (0, TILE - 1), 1)
    # Bottom + right shadow.
    pygame.draw.line(s, _shade(edge, 0.85), (0, TILE - 1), (TILE - 1, TILE - 1), 1)
    pygame.draw.line(s, _shade(edge, 0.85), (TILE - 1, 0), (TILE - 1, TILE - 1), 1)
    # Inner outline.
    pygame.draw.rect(s, edge, (1, 1, TILE - 2, TILE - 2), 1)
    # Mortar seam (depends on variant).
    seam_y = TILE // 2 if variant % 2 == 0 else TILE // 2 + 2
    pygame.draw.line(s, edge, (0, seam_y), (TILE - 1, seam_y), 1)
    pygame.draw.line(s, light, (0, seam_y + 1), (TILE - 1, seam_y + 1), 1)
    # Vertical seam offset by row.
    vx = TILE // 2 if variant % 2 == 0 else 0
    pygame.draw.line(s, edge, (vx, 0), (vx, seam_y), 1)
    vx2 = TILE - vx if vx else TILE // 2
    pygame.draw.line(s, edge, (vx2, seam_y + 1), (vx2, TILE - 1), 1)
    # Speckle noise.
    rng = random.Random(zone * 31 + variant + 7)
    for _ in range(8):
        x = rng.randint(2, TILE - 3); y = rng.randint(2, TILE - 3)
        c = rng.choice([light, edge])
        s.set_at((x, y), c)
    # Faint hieroglyph carving (rare).
    if variant % 5 == 0:
        cx, cy = TILE // 2, TILE // 2 + 4
        pygame.draw.circle(s, edge, (cx, cy), 4, 1)
        pygame.draw.line(s, edge, (cx - 5, cy + 6), (cx + 5, cy + 6), 1)
    return s


def _brick_block(zone: int, variant: int) -> pygame.Surface:
    s = pygame.Surface((TILE, TILE)).convert()
    base = R.STONE if zone < 2 else R.STONE_LIGHT
    edge = R.STONE_DARK
    light = _shade(base, 1.18)
    s.fill(base)
    pygame.draw.line(s, light, (0, 0), (TILE - 1, 0), 1)
    pygame.draw.line(s, light, (0, 0), (0, TILE - 1), 1)
    pygame.draw.line(s, _shade(edge, 0.7), (0, TILE - 1), (TILE - 1, TILE - 1), 1)
    pygame.draw.line(s, _shade(edge, 0.7), (TILE - 1, 0), (TILE - 1, TILE - 1), 1)
    pygame.draw.rect(s, edge, (1, 1, TILE - 2, TILE - 2), 1)
    # Brick rows.
    for row in range(4):
        y = row * (TILE // 4)
        pygame.draw.line(s, edge, (0, y), (TILE - 1, y), 1)
        # Stagger vertical seams.
        seam_x = (row * 9 + variant * 5) % TILE
        pygame.draw.line(s, edge, (seam_x, y),
                         (seam_x, y + TILE // 4), 1)
    return s


def _forge_block(variant: int) -> pygame.Surface:
    s = pygame.Surface((TILE, TILE)).convert()
    s.fill(R.COPPER)
    # Bevel.
    pygame.draw.line(s, R.COPPER_LIGHT, (0, 0), (TILE - 1, 0), 1)
    pygame.draw.line(s, R.COPPER_LIGHT, (0, 0), (0, TILE - 1), 1)
    pygame.draw.line(s, R.EMBER_DIM, (0, TILE - 1), (TILE - 1, TILE - 1), 1)
    pygame.draw.line(s, R.EMBER_DIM, (TILE - 1, 0), (TILE - 1, TILE - 1), 1)
    pygame.draw.rect(s, R.EMBER_DIM, (1, 1, TILE - 2, TILE - 2), 1)
    # Inner glow ribbon.
    pygame.draw.rect(s, R.EMBER, (4, TILE - 8, TILE - 8, 3))
    pygame.draw.rect(s, R.GLYPH_GLOW_S, (5, TILE - 7, TILE - 10, 1))
    # Rivets.
    for (rx, ry) in [(4, 4), (TILE - 5, 4), (4, TILE - 5), (TILE - 5, TILE - 5)]:
        pygame.draw.circle(s, R.EMBER_DIM, (rx, ry), 2)
        pygame.draw.circle(s, R.GLYPH_GLOW, (rx - 1, ry - 1), 1)
    # Variant: gear emboss in some tiles.
    if variant % 3 == 0:
        cx, cy = TILE // 2, TILE // 2
        pygame.draw.circle(s, R.EMBER_DIM, (cx, cy), 6, 1)
        for i in range(8):
            a = i * (math.pi / 4)
            ex = cx + int(math.cos(a) * 7)
            ey = cy + int(math.sin(a) * 7)
            s.set_at((ex, ey), R.GLYPH_GLOW)
    return s


def _spike_tile(zone: int) -> pygame.Surface:
    s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    # Plinth.
    plinth_color = R.STONE_DARK if zone != 1 else R.EMBER_DIM
    pygame.draw.rect(s, plinth_color, (0, TILE - 6, TILE, 6))
    pygame.draw.line(s, _shade(plinth_color, 1.4), (0, TILE - 6), (TILE - 1, TILE - 6), 1)
    # Spikes (3 metal teeth) with bright highlight.
    for i in range(3):
        cx = 6 + i * 10
        # Body.
        pygame.draw.polygon(s, R.BONE, [
            (cx, TILE - 6),
            (cx + 5, 4),
            (cx + 10, TILE - 6),
        ])
        # Highlight side.
        pygame.draw.polygon(s, (255, 245, 220), [
            (cx + 5, 4), (cx + 5, TILE - 6), (cx + 1, TILE - 6),
        ])
        # Shadow side.
        pygame.draw.polygon(s, _shade(R.BONE, 0.6), [
            (cx + 5, 4), (cx + 5, TILE - 6), (cx + 9, TILE - 6),
        ])
        pygame.draw.line(s, R.STONE_DARK,
                         (cx, TILE - 6), (cx + 5, 4), 1)
        pygame.draw.line(s, R.STONE_DARK,
                         (cx + 5, 4), (cx + 10, TILE - 6), 1)
    # Blood stain.
    s.set_at((11, 5), R.BLOOD)
    return s


def _crumble_tile(zone: int, variant: int) -> pygame.Surface:
    s = pygame.Surface((TILE, TILE)).convert()
    base = R.SAND_LIGHT
    edge = R.SANDSTONE_D
    s.fill(base)
    # Bevel.
    pygame.draw.line(s, (252, 230, 188), (0, 0), (TILE - 1, 0), 1)
    pygame.draw.line(s, (252, 230, 188), (0, 0), (0, TILE - 1), 1)
    pygame.draw.line(s, _shade(edge, 0.7), (0, TILE - 1), (TILE - 1, TILE - 1), 1)
    pygame.draw.line(s, _shade(edge, 0.7), (TILE - 1, 0), (TILE - 1, TILE - 1), 1)
    pygame.draw.rect(s, edge, (1, 1, TILE - 2, TILE - 2), 1)
    # Many cracks.
    rng = random.Random(variant)
    for _ in range(5):
        x1 = rng.randint(2, TILE - 3); y1 = rng.randint(2, TILE - 3)
        x2 = x1 + rng.randint(-8, 8); y2 = y1 + rng.randint(-8, 8)
        pygame.draw.line(s, edge, (x1, y1), (x2, y2), 1)
    # Crumb pebbles.
    for _ in range(4):
        x = rng.randint(3, TILE - 4); y = rng.randint(3, TILE - 4)
        s.set_at((x, y), R.STONE_DARK)
    return s


def _oneway_tile(zone: int) -> pygame.Surface:
    s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    if zone == 0:
        wood = (160, 110, 70); shadow = (90, 55, 30); light = (200, 150, 100)
    elif zone == 1:
        wood = R.GEAR_BRONZE; shadow = R.GEAR_BRONZE_D; light = R.COPPER_LIGHT
    else:
        wood = R.STONE_LIGHT; shadow = R.STONE_DARK; light = R.PARCHMENT
    pygame.draw.rect(s, wood, (0, 0, TILE, 7))
    pygame.draw.line(s, light, (0, 0), (TILE - 1, 0), 1)
    pygame.draw.line(s, shadow, (0, 6), (TILE - 1, 6), 1)
    # Wood grain / studs.
    for x in range(4, TILE, 8):
        pygame.draw.line(s, shadow, (x, 1), (x, 5), 1)
    for x in (4, TILE - 6):
        pygame.draw.circle(s, shadow, (x, 3), 1)
    return s


def _deco_tile(zone: int) -> pygame.Surface:
    s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    cx, cy = TILE // 2, TILE // 2
    color = R.GLYPH_GLOW
    # Outer ring.
    pygame.draw.circle(s, color, (cx, cy), 8, 1)
    # Cuneiform ticks.
    pygame.draw.line(s, color, (cx - 5, cy), (cx + 5, cy), 1)
    pygame.draw.line(s, color, (cx, cy - 5), (cx, cy + 5), 1)
    pygame.draw.line(s, color, (cx - 3, cy - 3), (cx + 3, cy + 3), 1)
    return s


def _build_tile_cache() -> None:
    if _TILE_CACHE:
        return
    for zone in (0, 1, 2):
        for variant in range(4):
            _TILE_CACHE[(T_STONE, zone, variant)] = _stone_block(zone, variant)
            _TILE_CACHE[(T_BRICK, zone, variant)] = _brick_block(zone, variant)
            _TILE_CACHE[(T_CRUMBLE, zone, variant)] = _crumble_tile(zone, variant)
            _TILE_CACHE[(T_FORGE, zone, variant)] = _forge_block(variant)
        _TILE_CACHE[(T_SPIKE, zone, 0)] = _spike_tile(zone)
        _TILE_CACHE[(T_ONEWAY, zone, 0)] = _oneway_tile(zone)
        _TILE_CACHE[(T_DECO, zone, 0)] = _deco_tile(zone)
    # Crumbling-state tint variants (red wash) for each crumble base.
    for zone in (0, 1, 2):
        for variant in range(4):
            base = _TILE_CACHE[(T_CRUMBLE, zone, variant)].copy()
            tint = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            tint.fill((220, 60, 40, 90))
            base.blit(tint, (0, 0))
            _TILE_CACHE[("crumbling", zone, variant)] = base


# ============================================================================
# Background sprite cache
# ============================================================================

_BG_CACHE: dict[str, pygame.Surface] = {}


def _build_sky_gradient(top, bot) -> pygame.Surface:
    s = pygame.Surface((SCREEN_W, SCREEN_H)).convert()
    for y in range(SCREEN_H):
        t = y / SCREEN_H
        c = R.lerp_color(top, bot, t)
        pygame.draw.line(s, c, (0, y), (SCREEN_W, y))
    return s


def _build_sun(zone: int) -> pygame.Surface:
    s = pygame.Surface((180, 180), pygame.SRCALPHA)
    if zone == 0:
        col_outer = (255, 200, 130, 30)
        col_mid   = (255, 220, 160, 90)
        col_disc  = (255, 240, 190)
    elif zone == 1:
        col_outer = (255, 110, 60, 50)
        col_mid   = (255, 150, 80, 110)
        col_disc  = (255, 200, 130)
    else:
        col_outer = (200, 220, 240, 40)
        col_mid   = (240, 240, 240, 90)
        col_disc  = (250, 250, 240)
    # Soft halo.
    for i, r in enumerate([90, 70, 55, 42]):
        col = col_outer if i < 2 else col_mid
        pygame.draw.circle(s, col, (90, 90), r)
    pygame.draw.circle(s, col_disc, (90, 90), 30)
    return s


def _build_cloud(rng: random.Random, zone: int, scale: float = 1.0) -> pygame.Surface:
    w = int(rng.randint(90, 150) * scale)
    h = int(rng.randint(28, 42) * scale)
    s = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
    if zone == 0:
        body = (250, 230, 200, 210); rim = (255, 248, 225, 230); shadow = (220, 195, 160, 200)
    elif zone == 1:
        # Forge zone: smoke clouds (soft warm grey) — readable against dark crimson sky.
        body = (170, 140, 130, 200); rim = (220, 190, 170, 220); shadow = (110, 80, 70, 180)
    else:
        body = (250, 250, 250, 230); rim = (255, 255, 255, 245); shadow = (210, 215, 225, 200)
    # Build a smooth elliptical body first.
    n_blobs = rng.randint(3, 5)
    centers = []
    for i in range(n_blobs):
        cx = int((i + 0.5) * w / n_blobs) + rng.randint(-3, 3)
        cy = h // 2 + rng.randint(-2, 2)
        cr = rng.randint(int(h * 0.5), int(h * 0.7))
        centers.append((cx, cy, cr))
    # Bottom shadow row.
    for cx, cy, cr in centers:
        pygame.draw.circle(s, shadow, (cx + 4, cy + 6), cr - 2)
    # Body.
    for cx, cy, cr in centers:
        pygame.draw.circle(s, body, (cx + 4, cy + 4), cr)
    # Rim highlight on top.
    for cx, cy, cr in centers:
        pygame.draw.circle(s, rim, (cx + 4, cy + 4 - cr // 3), max(2, cr // 3))
    return s


def _build_mountain_strip(zone: int) -> pygame.Surface:
    """A horizontally-tileable mountain silhouette strip 480 wide."""
    w, h = 480, 200
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    if zone == 0:
        col = (140, 95, 70, 150)
    elif zone == 1:
        col = (40, 24, 24, 200)
    else:
        col = (90, 110, 130, 170)
    rng = random.Random(zone * 17 + 3)
    # Build a polyline silhouette across the strip.
    points = [(0, h)]
    x = 0
    while x < w:
        peak_w = rng.randint(60, 110)
        peak_h = rng.randint(70, 150)
        points.append((x + peak_w // 2, h - peak_h))
        x += peak_w
    points.append((w, h))
    pygame.draw.polygon(s, col, points)
    # Bright ridge highlight.
    bright = (col[0] + 30, col[1] + 30, col[2] + 30, col[3])
    for i in range(1, len(points) - 1):
        pygame.draw.line(s, bright, points[i - 1], points[i], 1)
    return s


def _build_ziggurat_strip(zone: int) -> pygame.Surface:
    """A 320-wide tileable midground silhouette of stepped structures."""
    w, h = 320, 240
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    if zone == 0:
        col = (110, 75, 50, 200); rim = (170, 120, 80, 220)
    elif zone == 1:
        col = (35, 20, 20, 230); rim = (90, 50, 40, 230)
    else:
        col = (110, 130, 150, 220); rim = (180, 200, 220, 230)
    # Big stepped ziggurat.
    base_y = h
    cx = w // 2
    steps = 6
    step_w = 36
    step_h = 22
    for i in range(steps):
        rect_w = (steps - i) * step_w + 30
        rect_h = step_h
        rect = pygame.Rect(cx - rect_w // 2, base_y - (i + 1) * rect_h,
                           rect_w, rect_h)
        pygame.draw.rect(s, col, rect)
        pygame.draw.line(s, rim, (rect.left, rect.top),
                         (rect.right - 1, rect.top), 1)
    # Side towers.
    for sx in (40, w - 60):
        pygame.draw.rect(s, col, (sx, h - 100, 30, 100))
        pygame.draw.line(s, rim, (sx, h - 100), (sx + 30, h - 100), 1)
        pygame.draw.rect(s, col, (sx + 4, h - 110, 22, 12))
    # Forge variant: chimney plumes.
    if zone == 1:
        for sx in (60, w - 80):
            pygame.draw.rect(s, (200, 80, 40, 180), (sx, h - 130, 6, 30))
    # Workshop variant: parapets.
    if zone == 2:
        for x in range(0, w, 18):
            pygame.draw.rect(s, col, (x, h - 36, 8, 8))
    return s


def _build_bg_set(zone: int) -> dict:
    if zone == 0:
        sky = _build_sky_gradient(R.SKY_DAWN_TOP, R.SKY_DAWN_BOT)
    elif zone == 1:
        sky = _build_sky_gradient(R.SKY_FORGE_TOP, R.SKY_FORGE_BOT)
    else:
        sky = _build_sky_gradient(R.SKY_WORK_TOP, R.SKY_WORK_BOT)
    sun = _build_sun(zone)
    mountains = _build_mountain_strip(zone)
    zigg = _build_ziggurat_strip(zone)
    rng = random.Random(zone + 1)
    clouds = [_build_cloud(rng, zone, scale=rng.uniform(0.7, 1.3)) for _ in range(8)]
    return dict(sky=sky, sun=sun, mountains=mountains,
                ziggurat=zigg, clouds=clouds)


def _ensure_bg(zone: int) -> dict:
    key = f"bg_{zone}"
    if key not in _BG_CACHE:
        _BG_CACHE[key] = _build_bg_set(zone)  # type: ignore[assignment]
    return _BG_CACHE[key]  # type: ignore[return-value]


# ============================================================================
# World
# ============================================================================

@dataclass
class ActiveChunk:
    name: str
    zone: int
    x_off: int
    width_cols: int
    tiles: list[list[int]]
    crumble_timers: dict[tuple[int, int], float] = field(default_factory=dict)
    entity_ids: list[int] = field(default_factory=list)

    @property
    def width_px(self) -> int:
        return self.width_cols * TILE

    @property
    def right_px(self) -> int:
        return self.x_off + self.width_px


class World:
    def __init__(self, chunk_pool, entities) -> None:
        self.chunks_lib = chunk_pool
        self.entities = entities
        self.active: list[ActiveChunk] = []
        self.camera_x: float = 0.0
        self.scroll_speed: float = SCROLL_BASE
        self.distance: float = 0.0
        self._next_x: int = 0
        # Pre-build caches once.
        _build_tile_cache()
        for z in (0, 1, 2):
            _ensure_bg(z)

    def reset(self) -> None:
        self.active.clear()
        self.camera_x = 0.0
        self.scroll_speed = SCROLL_BASE
        self.distance = 0.0
        self._next_x = 0
        self._spawn_chunk(force_name="start")
        for _ in range(3):
            self._spawn_chunk()

    # ------------------------------------------------------------------
    def _zone_for(self, world_x: float) -> int:
        z = 0
        for i, threshold in enumerate(ZONE_THRESHOLDS):
            if world_x >= threshold:
                z = i
        return z

    @property
    def current_zone(self) -> int:
        return self._zone_for(self.camera_x + SCREEN_W * 0.5)

    def _spawn_chunk(self, force_name: Optional[str] = None) -> None:
        zone = self._zone_for(self._next_x)
        cdef = self.chunks_lib.get(force_name) if force_name else self.chunks_lib.random_for_zone(zone)
        ac = ActiveChunk(
            name=cdef.name, zone=zone, x_off=self._next_x,
            width_cols=cdef.width_cols,
            tiles=[row[:] for row in cdef.tiles],
        )
        self.active.append(ac)
        for spec in cdef.entities:
            self.entities.spawn_from_spec(spec, ac.x_off)
        self._next_x += ac.width_px

    def _trim_old_chunks(self) -> None:
        cutoff = self.camera_x - SCREEN_W * 0.5
        while self.active and self.active[0].right_px < cutoff:
            self.active.pop(0)

    # ------------------------------------------------------------------
    def update(self, dt: float, player_world_x: float) -> None:
        self.distance = max(self.distance, player_world_x)
        target = SCROLL_BASE + SCROLL_RAMP * (self.distance / 1000.0)
        self.scroll_speed = min(SCROLL_MAX, target)
        self.camera_x += self.scroll_speed * dt

        while self._next_x < self.camera_x + SCREEN_W * 1.6:
            self._spawn_chunk()
        self._trim_old_chunks()

        for ch in self.active:
            done = []
            for key, t in ch.crumble_timers.items():
                t -= dt
                if t <= 0:
                    done.append(key)
                else:
                    ch.crumble_timers[key] = t
            for key in done:
                col, row = key
                ch.tiles[row][col] = T_AIR
                ch.crumble_timers.pop(key, None)

    # ------------------------------------------------------------------
    # Tile / collision queries
    def tile_at(self, world_x: float, world_y: float) -> int:
        if world_y < 0 or world_y >= SCREEN_H:
            return T_AIR
        for ch in self.active:
            if ch.x_off <= world_x < ch.right_px:
                col = int((world_x - ch.x_off) // TILE)
                row = int(world_y // TILE)
                if 0 <= row < GRID_ROWS and 0 <= col < ch.width_cols:
                    return ch.tiles[row][col]
                return T_AIR
        return T_AIR

    def _chunk_and_local(self, world_x: float, world_y: float):
        for ch in self.active:
            if ch.x_off <= world_x < ch.right_px:
                col = int((world_x - ch.x_off) // TILE)
                row = int(world_y // TILE)
                return ch, col, row
        return None, 0, 0

    def is_solid(self, world_x: float, world_y: float) -> bool:
        return self.tile_at(world_x, world_y) in SOLID_TILES

    def is_oneway(self, world_x: float, world_y: float) -> bool:
        return self.tile_at(world_x, world_y) in ONEWAY_TILES

    def is_hazard(self, world_x: float, world_y: float) -> bool:
        return self.tile_at(world_x, world_y) in HAZARD_TILES

    def overlaps_solid(self, rect: pygame.Rect) -> bool:
        cols_min = rect.left // TILE
        cols_max = (rect.right - 1) // TILE
        rows_min = max(0, rect.top // TILE)
        rows_max = min(GRID_ROWS - 1, (rect.bottom - 1) // TILE)
        for col in range(cols_min, cols_max + 1):
            cx = col * TILE + TILE // 2
            for row in range(rows_min, rows_max + 1):
                cy = row * TILE + TILE // 2
                if self.tile_at(cx, cy) in SOLID_TILES:
                    return True
        return False

    def overlaps_hazard(self, rect: pygame.Rect) -> bool:
        cols_min = rect.left // TILE
        cols_max = (rect.right - 1) // TILE
        rows_min = max(0, rect.top // TILE)
        rows_max = min(GRID_ROWS - 1, (rect.bottom - 1) // TILE)
        for col in range(cols_min, cols_max + 1):
            cx = col * TILE + TILE // 2
            for row in range(rows_min, rows_max + 1):
                cy = row * TILE + TILE // 2
                if self.tile_at(cx, cy) in HAZARD_TILES:
                    return True
        return False

    def trigger_crumble(self, world_x: float, world_y: float) -> None:
        ch, col, row = self._chunk_and_local(world_x, world_y)
        if ch is None or row < 0 or row >= GRID_ROWS or col < 0 or col >= ch.width_cols:
            return
        if ch.tiles[row][col] != T_CRUMBLE:
            return
        if (col, row) in ch.crumble_timers:
            return
        ch.crumble_timers[(col, row)] = 0.45

    def trigger_crumble_under_rect(self, rect: pygame.Rect) -> None:
        probe_y = rect.bottom + 1
        cols_min = rect.left // TILE
        cols_max = (rect.right - 1) // TILE
        for col in range(cols_min, cols_max + 1):
            cx = col * TILE + TILE // 2
            self.trigger_crumble(cx, probe_y)

    # ------------------------------------------------------------------
    # Drawing
    def draw_background(self, surf: pygame.Surface) -> None:
        zone = self.current_zone
        bg = _ensure_bg(zone)
        surf.blit(bg["sky"], (0, 0))

        # Sun: parallax very slow, stays in upper-right.
        sun_x = SCREEN_W - 220 - int(self.camera_x * 0.02) % 600
        if sun_x < -180:
            sun_x = -180
        surf.blit(bg["sun"], (sun_x, 30))

        # Clouds: slow horizontal scroll.
        clouds = bg["clouds"]
        # Time-independent: tie to camera_x so they drift consistently.
        spacing = 320
        offset = int(self.camera_x * 0.08) % spacing
        for i, cloud in enumerate(clouds[:5]):
            x = -offset + i * spacing - 40
            y = 40 + (i * 23) % 80
            surf.blit(cloud, (x, y))

        # Far mountain layer.
        mts = bg["mountains"]
        mw = mts.get_width()
        offset = int(self.camera_x * 0.18) % mw
        for x in range(-offset, SCREEN_W + mw, mw):
            surf.blit(mts, (x, SCREEN_H - mts.get_height() - 80))

        # Mid ziggurat layer.
        zigg = bg["ziggurat"]
        zw = zigg.get_width()
        offset = int(self.camera_x * 0.4) % zw
        for x in range(-offset, SCREEN_W + zw, zw):
            surf.blit(zigg, (x, SCREEN_H - zigg.get_height() - 30))

        # Atmospheric haze near horizon.
        haze_color = R.lerp_color(R.SKY_DAWN_BOT if zone == 0
                                  else (R.SKY_FORGE_BOT if zone == 1 else R.SKY_WORK_BOT),
                                  (255, 255, 255), 0.25)
        haze = pygame.Surface((SCREEN_W, 50), pygame.SRCALPHA)
        for y in range(50):
            a = int(80 * (y / 50))
            pygame.draw.line(haze, (*haze_color, a), (0, y), (SCREEN_W, y))
        surf.blit(haze, (0, SCREEN_H - 110))

    def draw_tiles(self, surf: pygame.Surface) -> None:
        cam = int(self.camera_x)
        for ch in self.active:
            if ch.right_px < cam - TILE or ch.x_off > cam + SCREEN_W + TILE:
                continue
            for row in range(GRID_ROWS):
                py = row * TILE
                for col in range(ch.width_cols):
                    t = ch.tiles[row][col]
                    if t == T_AIR:
                        continue
                    px = ch.x_off + col * TILE - cam
                    if px < -TILE or px > SCREEN_W:
                        continue
                    crumbling = (col, row) in ch.crumble_timers
                    self._blit_tile(surf, t, px, py, ch.zone, col, row, crumbling)

    def _blit_tile(self, surf, t, px, py, zone, col, row, crumbling):
        # Variant from position (deterministic).
        v = (col * 7 + row * 13) % 4
        if t == T_CRUMBLE and crumbling:
            sprite = _TILE_CACHE.get(("crumbling", zone, v))
        else:
            sprite = _TILE_CACHE.get((t, zone, v if t in (T_STONE, T_BRICK, T_CRUMBLE, T_FORGE) else 0))
        if sprite is not None:
            surf.blit(sprite, (px, py))
            # If this is a TOP solid tile (no solid above), add a grass/ridge highlight.
            if t in (T_STONE, T_BRICK, T_FORGE):
                if row == 0 or self.tile_at(col * TILE + TILE // 2 + 0, (row - 1) * TILE + TILE // 2) not in SOLID_TILES:
                    self._draw_top_capping(surf, px, py, zone)

    def _draw_top_capping(self, surf, px, py, zone):
        # A 2-3px lit ridge on top of exposed surface tiles.
        if zone == 0:
            highlight = (252, 232, 188)
        elif zone == 1:
            highlight = (255, 200, 130)
        else:
            highlight = (250, 244, 220)
        pygame.draw.line(surf, highlight, (px, py), (px + TILE - 1, py), 2)
        # Tiny rocks on top.
        rng = random.Random(px * 31 + py)
        for _ in range(2):
            x = px + rng.randint(2, TILE - 4)
            pygame.draw.circle(surf, R.STONE_DARK, (x, py - 1), 1)
