"""Babel's Glyph — endless side-scrolling auto-runner (web build)."""
from __future__ import annotations
import asyncio
import sys
import pygame

from game.constants import SCREEN_W, SCREEN_H, TARGET_FPS
from game.input import Input
from game.player import Player
from game.world import World
from game.entities import EntityManager
from game.chunks import Chunks
from game.hud import HUD
from game import particles, audio


TITLE   = "title"
PLAYING = "playing"
DEAD    = "dead"

PIXELS_PER_METER = 50.0


class Game:
    def __init__(self) -> None:
        pygame.init()
        audio.init()
        pygame.display.set_caption("Babel's Glyph")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.input = Input()
        self.hud = HUD()
        self.scene = TITLE
        self.highscore_m = 0.0
        self._reset_world()

    def _reset_world(self) -> None:
        particles.reset()
        self.entities = EntityManager()
        self.chunks_lib = Chunks()
        self.world = World(self.chunks_lib, self.entities)
        self.world.reset()
        self.player = Player(120.0, 14 * 32 - 38)
        self._new_record_this_run = False

    def start_play(self) -> None:
        self._reset_world()
        self.scene = PLAYING

    # ------------------------------------------------------------------
    async def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(TARGET_FPS) / 1000.0
            if dt > 1 / 20:
                dt = 1 / 20

            self.input.begin_frame()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                self.input.handle_event(ev)

            # Esc quits on desktop; in the browser, bounce back to title.
            if self.input.quit_pressed:
                if sys.platform == "emscripten":
                    self.scene = TITLE
                else:
                    running = False

            if self.scene == TITLE:
                if self.input.start_pressed or self.input.restart_pressed:
                    self.start_play()
            elif self.scene == PLAYING:
                self._update_play(dt)
            elif self.scene == DEAD:
                if self.input.restart_pressed:
                    self.start_play()

            self._render()
            pygame.display.flip()

            # Yield to the browser's event loop (no-op on desktop).
            await asyncio.sleep(0)

        pygame.quit()

    def _update_play(self, dt: float) -> None:
        self.world.update(dt, self.player.x)
        self.player.update(dt, self.input, self.world, self.entities)
        self.entities.update_all(dt, self.world, self.player)
        particles.get().update(dt)

        if not self.player.alive:
            self.scene = DEAD
            run_m = self.world.distance / PIXELS_PER_METER
            if run_m > self.highscore_m:
                self.highscore_m = run_m
                self._new_record_this_run = True
                audio.get().play("record")
            else:
                audio.get().play("death")

        if self.input.restart_pressed:
            self.start_play()

    # ------------------------------------------------------------------
    def _render(self) -> None:
        self.world.draw_background(self.screen)
        self.world.draw_tiles(self.screen)
        self.entities.draw_all(self.screen, self.world.camera_x)
        self.player.draw(self.screen, self.world.camera_x)
        particles.get().draw(self.screen, self.world.camera_x)

        if self.scene == TITLE:
            self.hud.draw_title(self.screen, highscore=self.highscore_m if self.highscore_m else None)
        elif self.scene == PLAYING:
            self.hud.draw_playing(
                self.screen,
                hp=self.player.hp,
                max_hp=self.player.max_hp,
                glyphs=self.player.glyphs,
                distance_m=self.world.distance / PIXELS_PER_METER,
                zone_idx=self.world.current_zone,
                score=self.world.distance,
                highscore=self.highscore_m if self.highscore_m else None,
            )
        elif self.scene == DEAD:
            self.hud.draw_playing(
                self.screen,
                hp=0,
                max_hp=self.player.max_hp,
                glyphs=self.player.glyphs,
                distance_m=self.world.distance / PIXELS_PER_METER,
                zone_idx=self.world.current_zone,
                score=self.world.distance,
                highscore=self.highscore_m if self.highscore_m else None,
            )
            self.hud.draw_gameover(
                self.screen,
                distance_m=self.world.distance / PIXELS_PER_METER,
                glyphs=self.player.glyphs,
                highscore=self.highscore_m,
                new_record=self._new_record_this_run,
            )


async def main() -> None:
    await Game().run()


if __name__ == "__main__":
    asyncio.run(main())
