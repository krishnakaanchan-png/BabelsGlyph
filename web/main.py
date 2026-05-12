"""Babel's Glyph — endless side-scrolling auto-runner (web build)."""
from __future__ import annotations
import asyncio
import sys
import pygame

from game.constants import (
    SCREEN_W, SCREEN_H, WINDOW_W, WINDOW_H, RENDER_SCALE, TARGET_FPS,
)
from game.input import Input
from game.player import Player
from game.world import World
from game.entities import EntityManager
from game.chunks import Chunks
from game.hud import HUD
from game import particles, audio, music, profile, leaderboard, render as R


NAME    = "name"
TITLE   = "title"
PLAYING = "playing"
DEAD    = "dead"

# How many world pixels equal "one meter" for the distance display.
PIXELS_PER_METER = 50.0


class Game:
    def __init__(self) -> None:
        # Lock the mixer BEFORE pygame.init() to the same format as the
        # shipped music track. This avoids runtime resampling artifacts.
        pygame.mixer.pre_init(
            music.MIXER_SR,
            -16,
            music.MIXER_CHANNELS,
            music.MIXER_BUFFER,
        )
        pygame.init()
        audio.init()
        music.init()
        music.get().play()
        leaderboard.init()
        pygame.display.set_caption("Babel's Glyph")
        # Logical render surface stays at SCREEN_W x SCREEN_H so all
        # gameplay code keeps working unchanged. The OS window opens at
        # WINDOW_W x WINDOW_H (== SCREEN_* on web, 2x on desktop). The
        # bloom + vignette post-FX run on the logical frame so they look
        # identical regardless of the display scale.
        self.window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.screen = pygame.Surface((SCREEN_W, SCREEN_H)).convert()
        self._vignette = R.make_vignette(SCREEN_W, SCREEN_H)
        self.clock = pygame.time.Clock()
        self.input = Input(render_scale=RENDER_SCALE)
        self.hud = HUD()
        self.highscore_m = 0.0
        self._submitted_this_run = False
        self._reset_world()
        # Decide where to start: name entry on first launch, otherwise title.
        if profile.has_name():
            self.scene = TITLE
        else:
            self._enter_name_scene()

    def _reset_world(self) -> None:
        particles.reset()
        self.entities = EntityManager()
        self.chunks_lib = Chunks()
        self.world = World(self.chunks_lib, self.entities)
        self.world.reset()
        # Player starts on the start chunk's ground floor (row 14 top).
        self.player = Player(120.0, 14 * 32 - 38)
        self._new_record_this_run = False
        self._death_played = False
        self._submitted_this_run = False

    def start_play(self) -> None:
        self._reset_world()
        self.scene = PLAYING

    def _enter_name_scene(self) -> None:
        self.scene = NAME
        self.input.text_mode = True
        self.input.reset_text(initial=profile.get_name() if profile.has_name() else "")

    def _exit_name_scene(self) -> None:
        self.input.text_mode = False
        self.input.reset_text("")
        self.scene = TITLE

    # ------------------------------------------------------------------
    def _handle_audio_toggles(self) -> None:
        """M = music mute, N = SFX mute, mouse = click HUD icons."""
        if self.input.mute_music_pressed:
            music.get().toggle_muted()
        if self.input.mute_sfx_pressed:
            audio.get().toggle_muted()
        if self.input.click_xy is not None:
            target = self.hud.hit_test_audio_buttons(self.input.click_xy)
            if target == "music":
                music.get().toggle_muted()
            elif target == "sfx":
                audio.get().toggle_muted()

    # ------------------------------------------------------------------
    async def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(TARGET_FPS) / 1000.0
            if dt > 1 / 20:
                dt = 1 / 20

            self.input.begin_frame()
            for ev in pygame.event.get():
                self.input.handle_event(ev)
            # Combine keyboard + gamepad held states (and poll triggers)
            # AFTER the event pump so movement is up to date for this frame.
            self.input.end_frame()

            # Esc handling: in the browser we bounce back to title rather
            # than killing the tab; on desktop it quits.
            if self.scene != NAME and self.input.quit_pressed:
                if sys.platform == "emscripten":
                    self.scene = TITLE
                else:
                    running = False

            # Audio mute toggles work in any non-text scene.
            if self.scene != NAME:
                self._handle_audio_toggles()

            if self.scene == NAME:
                self._update_name_entry()
            elif self.scene == TITLE:
                if self.input.start_pressed or self.input.restart_pressed:
                    self.start_play()
                elif self.input.rename_pressed:
                    self._enter_name_scene()
            elif self.scene == PLAYING:
                self._update_play(dt)
            elif self.scene == DEAD:
                if self.input.restart_pressed or self.input.start_pressed:
                    self.start_play()

            self._render()
            self._present()

            # Yield to the browser's event loop. This is what makes the
            # tab responsive under pygbag/emscripten; on desktop it's a
            # near-zero-cost no-op.
            await asyncio.sleep(0)

        pygame.quit()

    def _present(self) -> None:
        """Bilinearly upscale the logical screen to the OS window.

        On the web build RENDER_SCALE is 1 so this is a single straight
        blit; the bloom and vignette have already been baked into the
        logical surface.
        """
        if RENDER_SCALE == 1:
            self.window.blit(self.screen, (0, 0))
        else:
            pygame.transform.smoothscale(
                self.screen, (WINDOW_W, WINDOW_H), self.window,
            )
        pygame.display.flip()

    def _update_name_entry(self) -> None:
        if self.input.text_submit:
            stored = profile.set_name(self.input.text_buffer)
            audio.get().play("glyph")
            self._exit_name_scene()
        elif self.input.text_cancel and profile.has_name():
            # Allow Esc to back out only if we already had a name.
            self._exit_name_scene()

    def _update_play(self, dt: float) -> None:
        # Order matters: world scroll first, then player, then entities.
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
            # Play the death/record sting exactly ONCE per run, and let
            # any overlapping SFX (hit/explode) finish naturally on their
            # own channels - we no longer stop them, since cutting a Sound
            # mid-playback can produce a hard click on some drivers.
            if not self._death_played:
                self._death_played = True
                if self._new_record_this_run:
                    audio.get().play("record")
                else:
                    audio.get().play("death")
            # Submit to the global leaderboard exactly once per run.
            if not self._submitted_this_run:
                self._submitted_this_run = True
                leaderboard.get().submit(
                    profile.get_name(),
                    int(run_m),
                    int(self.player.glyphs),
                )

        # Restart hotkey works mid-run.
        if self.input.restart_pressed:
            self.start_play()

    # ------------------------------------------------------------------
    def _render(self) -> None:
        # --- Gameplay layer (subject to bloom + vignette post-FX). -----
        self.world.draw_background(self.screen)
        self.world.draw_tiles(self.screen)
        self.entities.draw_all(self.screen, self.world.camera_x)
        self.player.draw(self.screen, self.world.camera_x)
        particles.get().draw(self.screen, self.world.camera_x)

        # Bloom and vignette enhance the gameplay frame only - they
        # would just smear/dim the HUD if applied after it.
        R.apply_bloom(self.screen)
        self.screen.blit(self._vignette, (0, 0))

        # --- HUD layer (drawn on top, untouched by post-FX). -----------
        board = leaderboard.get()
        scores = board.top(10)
        status = board.status()
        pname = profile.get_name() if profile.has_name() else None

        if self.scene == NAME:
            blink_on = (pygame.time.get_ticks() // 500) % 2 == 0
            self.hud.draw_name_entry(
                self.screen,
                current_text=self.input.text_buffer,
                blink_on=blink_on,
            )
        elif self.scene == TITLE:
            self.hud.draw_title(
                self.screen,
                highscore=self.highscore_m if self.highscore_m else None,
                scores=scores,
                player_name=pname,
                board_status=status,
                gamepad_connected=self.input.gamepad_connected,
            )
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
                scores=scores,
                player_name=pname,
                board_status=status,
                gamepad_connected=self.input.gamepad_connected,
            )

        # Audio buttons are drawn last so they sit on top of every overlay
        # (but not on the name-entry screen, where they'd be confusing).
        if self.scene != NAME:
            self.hud.draw_audio_buttons(
                self.screen,
                music_muted=music.get().muted,
                sfx_muted=audio.get().muted,
            )


def main() -> None:
    asyncio.run(Game().run())


if __name__ == "__main__":
    main()
