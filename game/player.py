"""Player: run, jump, double-jump, dash, slide, wall-slide, wall-jump, glyph-bomb."""
from __future__ import annotations
import math
import pygame

from .constants import TILE, SCREEN_W, SCREEN_H, START_HP, MAX_HP
from . import render as R
from . import particles
from . import audio as A


# Tunables.
GRAVITY        = 1900.0
MOVE_SPEED     = 230.0
ACCEL_GROUND   = 2400.0
ACCEL_AIR      = 1300.0
JUMP_VELOCITY  = -660.0
JUMP_CUT       = -260.0  # if jump released early, cap rising velocity
COYOTE_TIME    = 0.10
JUMP_BUFFER    = 0.12
MAX_FALL       = 950.0
WALL_SLIDE_VY  = 130.0
WALL_JUMP_VX   = 280.0
WALL_JUMP_VY   = -620.0
WALL_STICK_T   = 0.10  # short window where horizontal input is ignored after wall jump

DASH_SPEED     = 520.0
DASH_TIME      = 0.18
DASH_COOLDOWN  = 0.55

SLIDE_TIME     = 0.55
SLIDE_BOOST    = 280.0

INVULN_AFTER_HIT = 1.1

STAND_W = 22
STAND_H = 38
SLIDE_W = 28
SLIDE_H = 22

BOMB_VX = 360.0
BOMB_VY = -280.0
BOMB_COOLDOWN = 0.55

PLAYER_FRAME_RECTS = [
    (114, 80, 154, 214),
    (394, 78, 188, 218),
    (684, 78, 194, 218),
    (80, 352, 198, 230),
    (400, 342, 170, 240),
    (612, 384, 334, 198),
    (50, 700, 266, 166),
    (388, 658, 188, 216),
    (716, 656, 168, 218),
]


class Player:
    def __init__(self, world_x: float, world_y: float) -> None:
        self.x = float(world_x)
        self.y = float(world_y)
        self.vx = 0.0
        self.vy = 0.0
        self.w = STAND_W
        self.h = STAND_H

        self.facing = 1
        self.on_ground = False
        self.on_wall_dir = 0  # -1 left, +1 right, 0 not against wall
        self._coyote = 0.0
        self._jump_buf = 0.0
        self._jumps_left = 1   # +1 air jump available after leaving ground

        self._dash_t = 0.0
        self._dash_cd = 0.0
        self._dash_dir = 1
        self._dash_used_in_air = False

        self._sliding = False
        self._slide_t = 0.0

        self._wall_lock = 0.0    # ignore horizontal input briefly after wall jump
        self._wall_jump_dir = 0

        self._bomb_cd = 0.0

        self._invuln = 0.0
        self._anim_t = 0.0
        self._step_t = 0.0
        self._was_grounded = False
        self._fall_vy = 0.0  # tracks falling speed for landing impact

        self.hp = START_HP
        self.max_hp = MAX_HP
        self.glyphs = 0
        self.alive = True

    # ------------------------------------------------------------------
    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    @property
    def is_dashing(self) -> bool:
        return self._dash_t > 0

    @property
    def is_invuln(self) -> bool:
        return self._invuln > 0

    # ------------------------------------------------------------------
    def reset(self, world_x: float, world_y: float) -> None:
        self.__init__(world_x, world_y)

    def collect_glyph(self, n: int = 1) -> None:
        self.glyphs += n

    def heal(self, n: int = 1) -> None:
        self.hp = min(self.max_hp, self.hp + n)

    def take_hit(self, em) -> None:
        if self.is_invuln or self.is_dashing or not self.alive:
            return
        self.hp -= 1
        self._invuln = INVULN_AFTER_HIT
        A.get().play("hit")
        # Knock-back upward and away.
        self.vy = -260.0
        self.vx = -120.0 * (1 if self.facing > 0 else -1)
        if self.hp <= 0:
            self.alive = False

    def kill(self) -> None:
        self.hp = 0
        self.alive = False

    def bounce(self) -> None:
        """Stomp bounce."""
        self.vy = -360.0
        self._jumps_left = 1   # refund air jump after stomp
        A.get().play("stomp")

    def apply_steam_boost(self) -> None:
        # Continuous upward boost while inside the column.
        if self.vy > -360:
            self.vy = -360
        # Keep dash refreshed so player feels responsive.
        self._dash_used_in_air = False

    def launch(self, vx_boost: float, vy: float) -> None:
        self.vy = vy
        self.vx += vx_boost
        self._jumps_left = 1   # refund a jump after catapult
        self._dash_used_in_air = False
        A.get().play("catapult")

    # ------------------------------------------------------------------
    def update(self, dt: float, inp, world, em) -> None:
        if not self.alive:
            return
        self._anim_t += dt
        self._step_t += dt
        self._invuln = max(0.0, self._invuln - dt)
        self._dash_cd = max(0.0, self._dash_cd - dt)
        self._bomb_cd = max(0.0, self._bomb_cd - dt)
        self._wall_lock = max(0.0, self._wall_lock - dt)
        self._was_grounded = self.on_ground
        if not self.on_ground:
            self._fall_vy = max(self._fall_vy, self.vy)

        # ---- Slide handling ----
        want_slide = inp.down and self.on_ground and abs(self.vx) > 80 and not self._sliding
        if want_slide:
            self._sliding = True
            self._slide_t = SLIDE_TIME
            self.w, self.h = SLIDE_W, SLIDE_H
            # Push down to keep feet on ground.
            self.y += STAND_H - SLIDE_H
            # Slide forward boost.
            self.vx = (SLIDE_BOOST if self.facing > 0 else -SLIDE_BOOST)
            A.get().play("slide")
        if self._sliding:
            self._slide_t -= dt
            # Forced exit if timer expires or down released, but only if standing room available.
            wants_exit = self._slide_t <= 0 or not inp.down
            if wants_exit and self._can_stand(world):
                self._end_slide()

        # ---- Horizontal input ----
        if self._wall_lock > 0:
            # Wall-jump lock: keep horizontal velocity from the jump impulse, no input override.
            target_vx = self.vx
        elif self._sliding:
            target_vx = self.vx  # momentum-driven; we'll apply ground friction below
        elif inp.left and not inp.right:
            target_vx = -MOVE_SPEED
            self.facing = -1
        elif inp.right and not inp.left:
            target_vx = MOVE_SPEED
            self.facing = 1
        else:
            target_vx = 0.0

        accel = ACCEL_GROUND if self.on_ground else ACCEL_AIR
        if not self._sliding and self._wall_lock <= 0:
            if self.vx < target_vx:
                self.vx = min(target_vx, self.vx + accel * dt)
            elif self.vx > target_vx:
                self.vx = max(target_vx, self.vx - accel * dt)
        elif self._sliding and self.on_ground:
            # Slide friction: gentle slow-down.
            friction = 600.0
            if self.vx > 0:
                self.vx = max(0, self.vx - friction * dt)
            elif self.vx < 0:
                self.vx = min(0, self.vx + friction * dt)

        # ---- Dash ----
        if inp.dash_pressed and self._dash_cd <= 0 and self._dash_t <= 0:
            if self.on_ground or not self._dash_used_in_air:
                self._dash_t = DASH_TIME
                self._dash_cd = DASH_COOLDOWN
                self._dash_dir = self.facing
                if not self.on_ground:
                    self._dash_used_in_air = True
                self.vy = 0.0  # cancel vertical
                A.get().play("dash")
                # If sliding, end it.
                if self._sliding and self._can_stand(world):
                    self._end_slide()

        if self._dash_t > 0:
            self._dash_t -= dt
            self.vx = DASH_SPEED * self._dash_dir
        else:
            # Apply gravity (skipped during dash).
            # Wall-slide drag.
            if (not self.on_ground and self.on_wall_dir != 0 and self.vy > 0):
                self.vy = min(self.vy + GRAVITY * 0.4 * dt, WALL_SLIDE_VY)
            else:
                self.vy = min(MAX_FALL, self.vy + GRAVITY * dt)

        # ---- Jump / double-jump / wall-jump ----
        if inp.jump_pressed:
            self._jump_buf = JUMP_BUFFER

        if self.on_ground:
            self._coyote = COYOTE_TIME
            self._jumps_left = 1
            self._dash_used_in_air = False
        else:
            self._coyote = max(0.0, self._coyote - dt)

        if self._jump_buf > 0:
            if self._coyote > 0:
                # Ground jump.
                self.vy = JUMP_VELOCITY
                self._coyote = 0
                self._jump_buf = 0
                self.on_ground = False
                A.get().play("jump")
            elif self.on_wall_dir != 0:
                # Wall jump.
                self.vy = WALL_JUMP_VY
                self.vx = -self.on_wall_dir * WALL_JUMP_VX
                self._wall_lock = WALL_STICK_T
                self._wall_jump_dir = -self.on_wall_dir
                self.facing = -self.on_wall_dir
                self._jump_buf = 0
                self._jumps_left = 1   # allow one air jump after wall-jump
                self._dash_used_in_air = False
                A.get().play("wall_jump")
            elif self._jumps_left > 0:
                # Double / air jump.
                self.vy = JUMP_VELOCITY * 0.92
                self._jumps_left -= 1
                self._jump_buf = 0
                A.get().play("double_jump")
        else:
            self._jump_buf = max(0.0, self._jump_buf - dt)

        # Variable jump height: cut velocity if jump released while rising.
        if inp.jump_released and self.vy < JUMP_CUT:
            self.vy = JUMP_CUT

        # ---- Glyph bomb ----
        if inp.bomb_pressed and self._bomb_cd <= 0:
            self._bomb_cd = BOMB_COOLDOWN
            from .entities import GlyphBomb
            cx = self.x + self.w / 2
            cy = self.y + self.h / 3
            em.add(GlyphBomb(cx, cy, BOMB_VX * self.facing, BOMB_VY))
            A.get().play("bomb_throw")

        # ---- Move & collide ----
        self._move_and_collide(dt, world, em)

        # ---- Landing impact particles ----
        if self.on_ground and not self._was_grounded and self._fall_vy > 200:
            ps = particles.get()
            intensity = min(1.6, self._fall_vy / 600.0)
            ps.burst_landing(self.x + self.w / 2, self.y + self.h, intensity)
            A.get().play("land_hard" if intensity > 0.7 else "land_soft")
            self._fall_vy = 0.0
        elif self.on_ground:
            self._fall_vy = 0.0

        # ---- Footstep dust ----
        if self.on_ground and abs(self.vx) > 80 and not self._sliding:
            if self._step_t > 0.18:
                self._step_t = 0.0
                ps = particles.get()
                ps.add(particles.Particle(
                    self.x + self.w / 2 - self.facing * 4,
                    self.y + self.h - 1,
                    -self.facing * 30, -20,
                    life=0.3, color=(220, 200, 160), size=2.5,
                    gravity=300, drag=2.0,
                ))

        # ---- Slide dust ----
        if self._sliding and self.on_ground:
            ps = particles.get()
            for _ in range(2):
                ps.add(particles.Particle(
                    self.x + self.w / 2 - self.facing * 4,
                    self.y + self.h - 2,
                    -self.facing * 60, -30,
                    life=0.4, color=(220, 200, 160), size=3,
                    gravity=250, drag=2.0,
                ))

        # ---- Dash trail ----
        if self.is_dashing:
            particles.get().trail_dash(
                self.x + self.w / 2 - self._dash_dir * 6,
                self.y + self.h / 2,
            )

        # ---- Wall-slide sparks ----
        if (not self.on_ground and self.on_wall_dir != 0 and self.vy > 10
                and abs(self.vy - WALL_SLIDE_VY) < 60):
            import random as _random
            if _random.random() < 0.4:
                wx = self.x + (-2 if self.on_wall_dir < 0 else self.w + 2)
                particles.get().add(particles.Particle(
                    wx, self.y + self.h * 0.6,
                    -self.on_wall_dir * 60, -30,
                    life=0.3, color=(255, 220, 150), size=2,
                    gravity=200, kind="spark",
                ))

        # ---- Hazard tile damage (spikes etc.) ----
        if world.overlaps_hazard(self.rect):
            self.take_hit(em)

        # ---- Engulfed by left edge (auto-scroll death) ----
        if self.rect.right < world.camera_x + 4:
            self.kill()

        # ---- Fell below screen ----
        if self.y > SCREEN_H + 60:
            self.kill()

        # Update on_wall_dir for next frame.
        self._refresh_wall_state(world, em)

    def _can_stand(self, world) -> bool:
        # Check if there's space to expand back to standing height.
        if self.h == STAND_H:
            return True
        test = pygame.Rect(int(self.x), int(self.y - (STAND_H - SLIDE_H)), STAND_W, STAND_H)
        return not world.overlaps_solid(test)

    def _end_slide(self) -> None:
        self._sliding = False
        # Restore standing dimensions, anchored at the feet.
        self.y -= (STAND_H - SLIDE_H)
        self.w, self.h = STAND_W, STAND_H

    # ------------------------------------------------------------------
    def _move_and_collide(self, dt: float, world, em) -> None:
        # X axis.
        self.x += self.vx * dt
        if self.vx != 0:
            r = self.rect
            if world.overlaps_solid(r):
                # Resolve by stepping back along x.
                step = 1 if self.vx < 0 else -1
                while world.overlaps_solid(r) and abs(step) < TILE * 2:
                    self.x += step
                    r = self.rect
                self.vx = 0
            # Solid platform entities (gears, catapults).
            for plat in world.entities.solid_platforms():
                pr = plat.rect
                if r.colliderect(pr):
                    if self.vx > 0:
                        self.x = pr.left - self.w
                    elif self.vx < 0:
                        self.x = pr.right
                    self.vx = 0
                    r = self.rect

        # Y axis.
        prev_bottom = self.y + self.h
        self.y += self.vy * dt
        self.on_ground = False
        r = self.rect

        if world.overlaps_solid(r):
            if self.vy > 0:
                # Land: snap to top of overlapping tile.
                # Find lowest top among overlapping solid tiles.
                top = self._lowest_solid_top(world, r)
                if top is not None:
                    self.y = top - self.h
                    self.vy = 0
                    self.on_ground = True
                    # If we landed on a crumble tile, trigger collapse.
                    world.trigger_crumble_under_rect(self.rect)
            elif self.vy < 0:
                # Head bump.
                bot = self._highest_solid_bottom(world, r)
                if bot is not None:
                    self.y = bot
                    self.vy = 0
            r = self.rect

        # One-way platforms (only when descending and previously above).
        if self.vy >= 0:
            for col in range(r.left // TILE, (r.right - 1) // TILE + 1):
                for row in range(max(0, r.top // TILE), min(((r.bottom - 1) // TILE) + 1, SCREEN_H // TILE)):
                    cx = col * TILE + TILE // 2
                    cy = row * TILE + TILE // 2
                    if world.is_oneway(cx, cy):
                        plat_top = row * TILE
                        if prev_bottom <= plat_top + 1 and r.bottom >= plat_top:
                            self.y = plat_top - self.h
                            self.vy = 0
                            self.on_ground = True
                            r = self.rect

        # Ground probe (since pygame Rects exclude bottom edge).
        if not self.on_ground and self.vy >= 0:
            probe = pygame.Rect(r.left + 1, r.bottom, r.width - 2, 2)
            rows = [(probe.bottom - 1) // TILE, probe.top // TILE]
            rows = [rr for rr in rows if rr >= 0]
            for row in sorted(set(rows)):
                plat_top = row * TILE
                if abs(r.bottom - plat_top) <= 2:
                    any_oneway = False
                    for col in range(r.left // TILE, (r.right - 1) // TILE + 1):
                        cx = col * TILE + TILE // 2
                        cy = plat_top + TILE // 2
                        if world.is_oneway(cx, cy):
                            any_oneway = True
                            break
                    if any_oneway:
                        self.y = plat_top - self.h
                        self.vy = 0
                        self.on_ground = True
                        r = self.rect
                        break

        # Solid ground probe (since pygame Rects exclude bottom edge).
        if not self.on_ground and self.vy >= 0:
            probe = pygame.Rect(r.left + 1, r.bottom, r.width - 2, 2)
            if world.overlaps_solid(probe):
                # Find the topmost solid tile under our feet and snap to it.
                rows = [(probe.bottom - 1) // TILE, probe.top // TILE]
                rows = [rr for rr in rows if rr >= 0]
                for row in sorted(set(rows)):
                    plat_top = row * TILE
                    if abs(r.bottom - plat_top) <= 2:
                        # Verify any cell beneath us in this row is solid.
                        any_solid = False
                        for col in range(r.left // TILE, (r.right - 1) // TILE + 1):
                            cx = col * TILE + TILE // 2
                            cy = plat_top + TILE // 2
                            if world.is_solid(cx, cy):
                                any_solid = True
                                break
                        if any_solid:
                            self.y = plat_top - self.h
                            self.vy = 0
                            self.on_ground = True
                            world.trigger_crumble_under_rect(self.rect)
                            break

        # Solid platform entities (vertical resolution).
        if not self.on_ground or self.vy != 0:
            r = self.rect
            for plat in world.entities.solid_platforms():
                pr = plat.rect
                if r.colliderect(pr):
                    if self.vy >= 0 and prev_bottom <= pr.top + 4:
                        self.y = pr.top - self.h
                        self.vy = 0
                        self.on_ground = True
                        r = self.rect
                    elif self.vy < 0 and prev_bottom > pr.top:
                        self.y = pr.bottom
                        self.vy = 0
                        r = self.rect
        # Standing-on probe for entity platforms.
        if not self.on_ground:
            r = self.rect
            probe = pygame.Rect(r.left + 1, r.bottom, r.width - 2, 2)
            for plat in world.entities.solid_platforms():
                if probe.colliderect(plat.rect):
                    self.y = plat.rect.top - self.h
                    self.vy = 0
                    self.on_ground = True
                    break

    def _lowest_solid_top(self, world, r):
        cols = range(r.left // TILE, (r.right - 1) // TILE + 1)
        rows = range(max(0, r.top // TILE), ((r.bottom - 1) // TILE) + 1)
        best = None
        for row in rows:
            for col in cols:
                cx = col * TILE + TILE // 2
                cy = row * TILE + TILE // 2
                if world.is_solid(cx, cy):
                    top = row * TILE
                    if best is None or top < best:
                        best = top
        return best

    def _highest_solid_bottom(self, world, r):
        cols = range(r.left // TILE, (r.right - 1) // TILE + 1)
        rows = range(max(0, r.top // TILE), ((r.bottom - 1) // TILE) + 1)
        best = None
        for row in rows:
            for col in cols:
                cx = col * TILE + TILE // 2
                cy = row * TILE + TILE // 2
                if world.is_solid(cx, cy):
                    bot = row * TILE + TILE
                    if best is None or bot > best:
                        best = bot
        return best

    def _refresh_wall_state(self, world, em) -> None:
        if self.on_ground or self.vy < 0:
            self.on_wall_dir = 0
            return
        r = self.rect
        # Probe 2px to either side of body, mid-height.
        ly = r.top + r.height // 2
        left_solid = world.is_solid(r.left - 2, ly) or world.is_solid(r.left - 2, r.top + 4) or world.is_solid(r.left - 2, r.bottom - 4)
        right_solid = world.is_solid(r.right + 1, ly) or world.is_solid(r.right + 1, r.top + 4) or world.is_solid(r.right + 1, r.bottom - 4)
        if left_solid:
            self.on_wall_dir = -1
        elif right_solid:
            self.on_wall_dir = 1
        else:
            self.on_wall_dir = 0

    # ------------------------------------------------------------------
    def draw(self, surf: pygame.Surface, camera_x: float) -> None:
        r = self.rect
        sx = int(self.x - camera_x)
        sy = int(self.y)
        # Invulnerability flicker.
        if self._invuln > 0 and int(self._invuln * 20) % 2 == 0:
            return

        # Drop shadow on ground.
        if self.on_ground:
            shadow = pygame.Surface((r.w + 6, 6), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
            surf.blit(shadow, (sx - 3, sy + r.h - 3))

        # Dash trail (drawn behind body so body remains crisp).
        if self.is_dashing:
            for i in range(4):
                tx = sx - self._dash_dir * (i * 6 + 4)
                trail = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
                pygame.draw.rect(trail, (255, 210, 110, max(20, 90 - i * 20)),
                                 (0, 4, r.w, r.h - 4), border_radius=4)
                surf.blit(trail, (tx, sy))

        frame_idx = 0
        if self._invuln > 0:
            frame_idx = 7
        elif self._sliding:
            frame_idx = 6
        elif self.is_dashing:
            frame_idx = 5
        elif not self.on_ground and self.vy < 0:
            frame_idx = 3
        elif not self.on_ground:
            frame_idx = 4
        elif abs(self.vx) > 40:
            frame_idx = 1 + (int(self._anim_t * 12) % 2)
        frame = R.get_atlas_region("player_robed_runner.png", PLAYER_FRAME_RECTS[frame_idx])
        if frame is not None:
            sprite_h = 40 if not self._sliding else 24
            sprite_w = max(18, int(frame.get_width() * (sprite_h / frame.get_height())))
            if self.is_dashing:
                sprite_w = max(sprite_w, 50)
            sprite = pygame.transform.smoothscale(frame, (sprite_w, sprite_h))
            if self.facing < 0:
                sprite = pygame.transform.flip(sprite, True, False)
            foot_y = sy + r.h
            surf.blit(sprite, (sx + r.w // 2 - sprite_w // 2, foot_y - sprite_h))
            if not self.on_ground and self._jumps_left > 0 and not self.is_dashing:
                aura = pygame.Surface((r.w + 6, 4), pygame.SRCALPHA)
                pygame.draw.ellipse(aura, (*R.GLYPH_GLOW_S, 60), aura.get_rect())
                surf.blit(aura, (sx - 3, sy + r.h - 1))
            return

        if self._sliding:
            self._draw_sliding(surf, sx, sy, r)
            return

        # Standing / running render.
        # Robe body.
        body_top = sy + 14
        body = pygame.Rect(sx + 1, body_top, r.w - 2, r.h - 14)
        # Robe gradient: lighter on top.
        pygame.draw.rect(surf, R.LAPIS_LIGHT, body)
        lower = pygame.Rect(body.x, body.y + body.h // 3, body.w, body.h - body.h // 3)
        pygame.draw.rect(surf, R.LAPIS, lower)
        # Robe folds (vertical creases).
        pygame.draw.line(surf, (40, 30, 70),
                         (body.x + body.w // 3, body.top + 4),
                         (body.x + body.w // 3 - 1, body.bottom - 1), 1)
        pygame.draw.line(surf, (40, 30, 70),
                         (body.x + 2 * body.w // 3, body.top + 4),
                         (body.x + 2 * body.w // 3 + 1, body.bottom - 1), 1)
        # Robe outline.
        pygame.draw.rect(surf, R.STONE_DARK, body, 1)
        # Sash with copper buckle.
        sash_y = body.top + 8
        pygame.draw.rect(surf, R.COPPER, (body.left + 1, sash_y, body.w - 2, 4))
        pygame.draw.rect(surf, R.COPPER_LIGHT, (body.left + 1, sash_y, body.w - 2, 1))
        pygame.draw.rect(surf, R.GEAR_BRONZE_D, (body.centerx - 2, sash_y, 4, 4))
        # Glowing chest mark.
        glow_cx = body.centerx
        glow_cy = body.top + 16
        glow = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*R.GLYPH_GLOW_S, 130), (5, 5), 5)
        surf.blit(glow, (glow_cx - 5, glow_cy - 5))
        pygame.draw.circle(surf, R.GLYPH_GLOW_S, (glow_cx, glow_cy), 2)
        pygame.draw.line(surf, R.GLYPH_GLOW, (glow_cx - 2, glow_cy),
                         (glow_cx + 2, glow_cy), 1)
        # Hood / head.
        head_cx = sx + r.w // 2
        head_cy = sy + 8
        # Hood backing (lapis hood arc behind).
        hood = pygame.Rect(sx, sy, r.w, 14)
        pygame.draw.ellipse(surf, R.LAPIS_LIGHT, hood)
        pygame.draw.ellipse(surf, R.STONE_DARK, hood, 1)
        # Face oval (lighter than full circle).
        face = pygame.Rect(head_cx - 5, head_cy - 5, 10, 11)
        pygame.draw.ellipse(surf, R.BONE, face)
        pygame.draw.ellipse(surf, (210, 180, 130), face, 1)
        # Hood shadow on face.
        pygame.draw.line(surf, (180, 150, 110),
                         (face.left + 1, face.top + 1),
                         (face.right - 2, face.top + 1), 1)
        # Eye.
        eye_x = head_cx + (2 * self.facing)
        pygame.draw.circle(surf, R.STONE_DARK, (eye_x, head_cy - 1), 1)
        # Hood drape on the back.
        drape_x = head_cx + (-r.w // 2 + 1 if self.facing > 0 else r.w // 2 - 1)
        drape_dir = -self.facing
        pygame.draw.polygon(surf, R.LAPIS, [
            (drape_x, head_cy - 2),
            (drape_x + drape_dir * 4, head_cy + 2),
            (drape_x + drape_dir * 2, head_cy + 6),
            (drape_x, head_cy + 4),
        ])
        # Arms (small lapis sleeves at robe sides).
        arm_y = body.top + 6
        arm_len = 6 + (int(2 * math.sin(self._anim_t * 14)) if abs(self.vx) > 30 and self.on_ground else 0)
        if self.facing > 0:
            pygame.draw.rect(surf, R.LAPIS_LIGHT, (body.left - 2, arm_y, 3, arm_len))
            pygame.draw.rect(surf, R.LAPIS, (body.right - 1, arm_y, 3, arm_len + 2))
        else:
            pygame.draw.rect(surf, R.LAPIS, (body.left - 2, arm_y, 3, arm_len + 2))
            pygame.draw.rect(surf, R.LAPIS_LIGHT, (body.right - 1, arm_y, 3, arm_len))
        # Feet anim.
        feet_y = sy + r.h - 4
        offset = 0
        if self.on_ground and abs(self.vx) > 10:
            offset = int(3 * math.sin(self._anim_t * 16))
        pygame.draw.rect(surf, R.STONE_DARK, (sx + 2, feet_y, 7, 4))
        pygame.draw.rect(surf, (60, 40, 30), (sx + 2, feet_y, 7, 1))
        pygame.draw.rect(surf, R.STONE_DARK, (sx + r.w - 9, feet_y - offset, 7, 4))
        pygame.draw.rect(surf, (60, 40, 30), (sx + r.w - 9, feet_y - offset, 7, 1))

        # Wall-slide shimmer (subtle, particles handle most of the FX).
        if not self.on_ground and self.on_wall_dir != 0 and self.vy > 10:
            shx = sx + (-2 if self.on_wall_dir < 0 else r.w + 2)
            for i in range(3):
                pygame.draw.line(surf, R.SAND_LIGHT,
                                 (shx, sy + 8 + i * 10), (shx, sy + 12 + i * 10), 1)

        # Mid-air aura when double-jumping/dash-ready.
        if not self.on_ground and self._jumps_left > 0 and not self.is_dashing:
            aura = pygame.Surface((r.w + 6, 4), pygame.SRCALPHA)
            pygame.draw.ellipse(aura, (*R.GLYPH_GLOW_S, 60), aura.get_rect())
            surf.blit(aura, (sx - 3, sy + r.h - 1))

    def _draw_sliding(self, surf, sx, sy, r):
        # Compact horizontal body during slide.
        body = pygame.Rect(sx + 1, sy + 4, r.w - 2, r.h - 4)
        pygame.draw.rect(surf, R.LAPIS, body)
        pygame.draw.rect(surf, R.LAPIS_LIGHT, body, 1)
        # Robe streak.
        streak_x = sx + (r.w - 4 if self.facing > 0 else 4)
        pygame.draw.line(surf, R.LAPIS_LIGHT,
                         (streak_x, body.top + 2), (streak_x, body.bottom - 2), 1)
        # Head ahead.
        head_x = sx + (r.w - 8 if self.facing > 0 else 8)
        pygame.draw.circle(surf, R.LAPIS_LIGHT, (head_x, sy + 8), 8)
        pygame.draw.circle(surf, R.BONE, (head_x, sy + 9), 5)
        eye_x = head_x + self.facing * 2
        pygame.draw.circle(surf, R.STONE_DARK, (eye_x, sy + 8), 1)
        # Glyph glow trail.
        for i in range(3):
            cx = sx + r.w // 2 - self.facing * (i * 6 + 6)
            _surf = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(_surf, (*R.GLYPH_GLOW_S, max(30, 100 - i * 30)), (4, 4), 4)
            surf.blit(_surf, (cx - 4, sy + r.h // 2 - 4))
