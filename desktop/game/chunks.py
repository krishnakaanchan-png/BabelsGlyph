"""Chunk library: hand-authored level segments parsed from ASCII art.

Each chunk is a dict with:
- name: str
- zone: int (0 outskirts, 1 forge, 2 workshop)
- tile_grid: list[str] of equal-width rows; chars decode to tile codes
- entities: parsed from ENTITY chars and EXTRA spec list

Tile chars in tile rows:
  '.' = air
  '#' = stone (zoned variant)
  'B' = brick (dark, neutral)
  'F' = forge stone (only zone 1)
  '^' = spike
  '~' = crumbling tile
  '-' = one-way platform
  '*' = decorative glyph

Entity chars (rendered in the tile grid in place of '.', occupying air):
  'g' = glyph pickup (score)
  'h' = heart pickup
  'a' = bronze automaton (walks left-right on platform below)
  'c' = catapult pad
  's' = steam jet (vertical column upward from this tile)
  'p' = rotating gear platform centered here
  'r' = rail platform anchor (paired with another 'r' to define endpoints)
  'm' = mirror beam emitter (horizontal beam to the right)
  'n' = cannon (fires bolts to the left periodically)
  'f' = fire piston gate emitter (left wall, fires right)
  'F' inside tile rows still means forge stone tile (we only treat 'F' as entity in extras)

Chunks are 20 tiles wide by GRID_ROWS (17) tall.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import random

from .constants import (
    TILE, GRID_ROWS,
    T_AIR, T_STONE, T_BRICK, T_SPIKE, T_CRUMBLE, T_ONEWAY, T_FORGE, T_DECO,
)


CHUNK_W = 20  # all chunks are 20 tiles wide for predictable streaming


@dataclass
class EntitySpec:
    kind: str
    col: int
    row: int
    params: dict = field(default_factory=dict)


@dataclass
class ChunkDef:
    name: str
    zone: int
    width_cols: int
    tiles: list[list[int]]
    entities: list[EntitySpec]


def _parse(name: str, zone: int, rows: list[str], extras: list[EntitySpec] | None = None) -> ChunkDef:
    extras = list(extras or [])
    assert len(rows) == GRID_ROWS, f"chunk {name} must have {GRID_ROWS} rows, got {len(rows)}"
    width = len(rows[0])
    assert all(len(r) == width for r in rows), f"chunk {name} rows must be equal width"

    tile_grid: list[list[int]] = [[T_AIR] * width for _ in range(GRID_ROWS)]
    entity_list: list[EntitySpec] = []
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch == '.':
                tile_grid[r][c] = T_AIR
            elif ch == '#':
                tile_grid[r][c] = T_STONE
            elif ch == 'B':
                tile_grid[r][c] = T_BRICK
            elif ch == 'F':
                tile_grid[r][c] = T_FORGE
            elif ch == '^':
                tile_grid[r][c] = T_SPIKE
            elif ch == '~':
                tile_grid[r][c] = T_CRUMBLE
            elif ch == '-':
                tile_grid[r][c] = T_ONEWAY
            elif ch == '*':
                tile_grid[r][c] = T_DECO
            else:
                # Treat as entity occupying air.
                tile_grid[r][c] = T_AIR
                if ch == 'g':
                    entity_list.append(EntitySpec("glyph", c, r))
                elif ch == 'h':
                    entity_list.append(EntitySpec("heart", c, r))
                elif ch == 'a':
                    entity_list.append(EntitySpec("automaton", c, r))
                elif ch == 'c':
                    entity_list.append(EntitySpec("catapult", c, r))
                elif ch == 's':
                    entity_list.append(EntitySpec("steam", c, r))
                elif ch == 'p':
                    entity_list.append(EntitySpec("gear", c, r))
                elif ch == 'm':
                    entity_list.append(EntitySpec("mirror", c, r))
                elif ch == 'n':
                    entity_list.append(EntitySpec("cannon", c, r))
                elif ch == 'f':
                    entity_list.append(EntitySpec("firepiston", c, r))
                # Rail platforms come from extras to specify endpoints.
    entity_list.extend(extras)
    return ChunkDef(name=name, zone=zone, width_cols=width,
                    tiles=tile_grid, entities=entity_list)


# ============================================================================
# CHUNK DEFINITIONS
# Convention: row 0 is top of screen, row 16 is bottom (17 rows total).
# Floor lives around row 13-14 (y=416..480). Lava/death is below row 16.
# ============================================================================


# --- Zone 0: Sandstone Outskirts ---

START = _parse("start", 0, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    ".....*..............",
    "....................",
    "....................",
    "....................",
    "..........g..g..g...",
    "....................",
    "####################",
    "####################",
    "####################",
])

S0_GAP = _parse("s0_gap", 0, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..........g.........",
    "....................",
    "....................",
    "....................",
    "######......########",
    "######......########",
    "######......########",
])

S0_SPIKES = _parse("s0_spikes", 0, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..g..............g..",
    "....................",
    "....................",
    "....................",
    "####..####..####..##",
    "####^^####^^####^^##",
    "####################",
])

S0_AUTO = _parse("s0_auto", 0, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..........g.........",
    "....a.....a.........",
    "....................",
    "....................",
    "####################",
    "####################",
    "####################",
])

S0_PLATFORMS = _parse("s0_platforms", 0, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "...........g........",
    ".......-----........",
    "....................",
    ".g..................",
    "....................",
    "..---...............",
    "....................",
    ".....g..............",
    "####....######...###",
    "####....######...###",
    "####################",
])

S0_CRUMBLE = _parse("s0_crumble", 0, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..........g.........",
    "....................",
    "....................",
    "....................",
    "...~~~~~~~~~~~~~....",
    "##..............####",
    "##^^^^^^^^^^^^^^^^##",
    "####################",
])

S0_CATAPULT = _parse("s0_catapult", 0, [
    "....................",
    "....................",
    "....................",
    "....................",
    "............g.......",
    "...........-----....",
    "....................",
    "....................",
    "....................",
    "..........g.........",
    "....................",
    "....................",
    "....................",
    "....................",
    "######....c.....####",
    "######..######..####",
    "####################",
])


# --- Zone 1: Da Vinci's Forge ---

S1_INTRO = _parse("s1_intro", 1, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..........g.........",
    "....................",
    "....................",
    "....................",
    "FFFF.FFFFFFFF.FFFFFF",
    "FFFF^FFFFFFFF^FFFFFF",
    "FFFFFFFFFFFFFFFFFFFF",
])

S1_GEAR = _parse("s1_gear", 1, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....g....p....g.....",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "###..........#######",
    "###^^^^^^^^^^#######",
    "FFFFFFFFFFFFFFFFFFFF",
])

S1_FIREPISTON = _parse("s1_firepiston", 1, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "Ff..............f..F",
    "Ff......g.......f..F",
    "F...............F..F",
    "FFFF##########FFFFFF",
    "FFFF##########FFFFFF",
    "FFFFFFFFFFFFFFFFFFFF",
])

S1_CANNON = _parse("s1_cannon", 1, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..........g.........",
    "....................",
    "....................",
    ".................n..",
    "FFFF########FFFF.FFF",
    "FFFF########FFFF^FFF",
    "FFFFFFFFFFFFFFFFFFFF",
])

S1_AUTOS = _parse("s1_autos", 1, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....g.......g.......",
    "....a.......a...h...",
    "....................",
    "....................",
    "FFFFFFFF##FFFFFFFFFF",
    "FFFFFFFF##FFFFFFFFFF",
    "FFFFFFFFFFFFFFFFFFFF",
])

S1_STEAM = _parse("s1_steam", 1, [
    "....................",
    ".................g..",
    "....................",
    "....................",
    "....................",
    "....................",
    ".......g............",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....s..........s....",
    "FFFF#FFFFFFFFFF#FFFF",
    "FFFFFFFFFFFFFFFFFFFF",
    "FFFFFFFFFFFFFFFFFFFF",
])


# --- Zone 2: Sky Workshop ---

S2_INTRO = _parse("s2_intro", 2, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..........g.........",
    "....................",
    "....................",
    "....................",
    "BBBB##BB##BB##BB##BB",
    "BBBB##BB##BB##BB##BB",
    "BBBBBBBBBBBBBBBBBBBB",
])

S2_PLATFORMS = _parse("s2_platforms", 2, [
    "....................",
    "....................",
    "....................",
    ".......g............",
    "....---------.......",
    "....................",
    "............g.......",
    ".........-----------",
    "....................",
    "...g................",
    "------..............",
    "....................",
    "....................",
    "....................",
    "BBB...........###BBB",
    "BBB^^^^^^^^^^^###BBB",
    "BBBBBBBBBBBBBBBBBBBB",
])

S2_MIRROR = _parse("s2_mirror", 2, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..m.................",
    "....................",
    "....................",
    "..........g.........",
    "....................",
    "....................",
    "....................",
    "BBBBBBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBBBBBB",
])

S2_GEARS_RAILS = _parse("s2_gears_rails", 2, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....g....p..........",
    "....................",
    "....................",
    "............p..g....",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "BBB.............BBBB",
    "BBB^^^^^^^^^^^^^BBBB",
    "BBBBBBBBBBBBBBBBBBBB",
])

S2_GAUNTLET = _parse("s2_gauntlet", 2, [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "...........g........",
    "...........-----....",
    "....................",
    "..g.................",
    "..-----.............",
    "....................",
    "............h.......",
    "....................",
    ".....c..............",
    "BBB.....##.....c.BBB",
    "BBB^^^^^##^^^^^^^BBB",
    "BBBBBBBBBBBBBBBBBBBB",
])


# Pool tagged by zone.
ZONE_CHUNKS: dict[int, list[ChunkDef]] = {
    0: [S0_GAP, S0_SPIKES, S0_AUTO, S0_PLATFORMS, S0_CRUMBLE, S0_CATAPULT],
    1: [S1_INTRO, S1_GEAR, S1_FIREPISTON, S1_CANNON, S1_AUTOS, S1_STEAM],
    2: [S2_INTRO, S2_PLATFORMS, S2_MIRROR, S2_GEARS_RAILS, S2_GAUNTLET],
}
NAMED: dict[str, ChunkDef] = {
    "start": START,
}


class Chunks:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._recent: list[str] = []

    def get(self, name: str) -> ChunkDef:
        if name in NAMED:
            return NAMED[name]
        for pool in ZONE_CHUNKS.values():
            for c in pool:
                if c.name == name:
                    return c
        raise KeyError(name)

    def random_for_zone(self, zone: int) -> ChunkDef:
        zone = max(0, min(zone, max(ZONE_CHUNKS.keys())))
        # Allow some bleed: 30% chance to pull from a lower zone for variety.
        pool = list(ZONE_CHUNKS[zone])
        if zone > 0 and self._rng.random() < 0.25:
            pool += ZONE_CHUNKS[zone - 1]
        # Avoid immediate repetition of the last 2 chunks.
        choice = self._rng.choice(pool)
        attempts = 0
        while choice.name in self._recent[-2:] and attempts < 6:
            choice = self._rng.choice(pool)
            attempts += 1
        self._recent.append(choice.name)
        if len(self._recent) > 6:
            self._recent.pop(0)
        return choice
