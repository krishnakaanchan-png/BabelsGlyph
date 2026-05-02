"""Shared constants for the endless runner."""

TILE         = 32
SCREEN_W     = 960
SCREEN_H     = 544          # 17 tiles tall (kept multiple of TILE)
GRID_COLS    = SCREEN_W // TILE   # 30
GRID_ROWS    = SCREEN_H // TILE   # 17
TARGET_FPS   = 60

# Auto-scroll: pixels per second.
SCROLL_BASE  = 90.0
SCROLL_MAX   = 220.0
SCROLL_RAMP  = 6.0        # additional px/s added per 1000 px of distance

# Gameplay.
START_HP     = 3
MAX_HP       = 5

# Zones (themed biomes), unlocked by distance in pixels.
ZONE_THRESHOLDS = [0, 3000, 8000]   # zone 0,1,2 unlock points

# Tile codes.
T_AIR     = 0
T_STONE   = 1   # solid sandstone block
T_BRICK   = 2   # solid darker brick (visual variant, same physics)
T_SPIKE   = 3   # damages on contact
T_CRUMBLE = 4   # solid until stepped on, then collapses
T_ONEWAY  = 5   # passable from below, solid from above
T_FORGE   = 6   # forge stone (visual variant)
T_DECO    = 7   # decorative, non-solid

SOLID_TILES   = {T_STONE, T_BRICK, T_CRUMBLE, T_FORGE}
ONEWAY_TILES  = {T_ONEWAY}
HAZARD_TILES  = {T_SPIKE}
