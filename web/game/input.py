"""Keyboard + Xbox-controller input mapping for the endless runner.

The public attribute surface (`left`, `right`, `down`, `jump_pressed`, ...)
is unchanged from the keyboard-only version; gameplay code keeps working.
We layer a gamepad on top by tracking pad-held states separately and
ORing them into the public flags each frame, while pad button presses
fire the same edge-triggered events as their keyboard equivalents.

Mapping (Xbox-style, SDL2 default layout):

    Left stick / D-pad ............... move left / right, slide (down)
    A (button 0) ..................... jump / start / confirm
    B (button 1) ..................... cancel (text mode) / restart
    X (button 2) ..................... bomb
    Y (button 3) ..................... mute music
    LB / RB (4 / 5) .................. dash
    Back / View (6) .................. mute SFX
    Start / Menu (7) ................. start / restart
    LT / RT (axes) ................... dash (alternate)

Some Windows drivers expose Xbox controllers with slightly different
layouts; the bindings above match SDL2's default game-controller mapping
which pygame-ce's joystick API receives unmodified.
"""
from __future__ import annotations
import pygame


# Button indices (SDL2 game-controller default, matches Xbox layout).
BTN_A = 0
BTN_B = 1
BTN_X = 2
BTN_Y = 3
BTN_LB = 4
BTN_RB = 5
BTN_BACK = 6
BTN_START = 7

# Axis indices.
AXIS_LX = 0   # Left stick X
AXIS_LY = 1   # Left stick Y
AXIS_LT = 4   # Left trigger (some drivers expose at 2)
AXIS_RT = 5   # Right trigger

# Dead-zone for analog sticks (0..1).
STICK_DEADZONE = 0.45
# Trigger pull threshold (-1.0 rest, +1.0 fully pressed on most drivers).
TRIGGER_THRESHOLD = 0.3


class Input:
    def __init__(self, render_scale: int = 1) -> None:
        # The OS window is `render_scale`x larger than the logical render
        # surface, but the HUD's hit boxes are in logical coords - so we
        # divide every incoming mouse position by render_scale before we
        # store it. Audio buttons and any other clickables work without
        # change after this transform.
        self._render_scale = max(1, int(render_scale))
        # Public combined held states (keyboard OR pad).
        self.left = False
        self.right = False
        self.down = False
        # Edge-triggered (one-shot) flags reset each frame in begin_frame().
        self.jump_pressed = False
        self.jump_released = False
        self.dash_pressed = False
        self.bomb_pressed = False
        self.restart_pressed = False
        self.start_pressed = False
        self.quit_pressed = False
        # Audio mute toggles.
        self.mute_music_pressed = False
        self.mute_sfx_pressed = False
        # Profile / leaderboard hotkeys.
        self.rename_pressed = False
        # Mouse click coords this frame (None if no click).
        self.click_xy: tuple[int, int] | None = None
        # ----- Text-input mode (for the name-entry screen) -----
        # When True, gameplay key bindings are suppressed and printable
        # keys are appended to ``text_buffer`` instead.
        self.text_mode: bool = False
        self.text_buffer: str = ""
        self.text_submit: bool = False
        self.text_cancel: bool = False

        # ----- Internal split state (so kb releases don't cancel pad-held) ---
        self._kb_left = False
        self._kb_right = False
        self._kb_down = False
        self._pad_left = False
        self._pad_right = False
        self._pad_down = False
        self._hat_left = False
        self._hat_right = False
        self._hat_down = False
        self._trigger_held = False  # rising-edge tracker for LT/RT dash

        # ----- Gamepad ------------------------------------------------------
        self._joy: pygame.joystick.Joystick | None = None
        self._joy_present = False
        self._init_joystick()

    # ------------------------------------------------------------------
    def _init_joystick(self) -> None:
        """Open the first connected joystick, if any. Safe if none plugged."""
        try:
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self._joy = pygame.joystick.Joystick(0)
                self._joy.init()
                self._joy_present = True
        except Exception:
            self._joy = None
            self._joy_present = False

    @property
    def gamepad_connected(self) -> bool:
        return self._joy_present

    def gamepad_name(self) -> str:
        if self._joy is None:
            return ""
        try:
            return self._joy.get_name()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    def begin_frame(self) -> None:
        self.jump_pressed = False
        self.jump_released = False
        self.dash_pressed = False
        self.bomb_pressed = False
        self.restart_pressed = False
        self.start_pressed = False
        self.mute_music_pressed = False
        self.mute_sfx_pressed = False
        self.rename_pressed = False
        self.click_xy = None
        self.text_submit = False
        self.text_cancel = False

    def end_frame(self) -> None:
        """Recompute combined held states from keyboard + pad sources.

        Call this AFTER all events have been pumped through ``handle_event``
        for the frame and BEFORE the gameplay update reads ``self.left`` etc.
        """
        self._poll_pad_axes()
        self.left = self._kb_left or self._pad_left
        self.right = self._kb_right or self._pad_right
        self.down = self._kb_down or self._pad_down

    def reset_text(self, initial: str = "") -> None:
        """Begin/clear text-entry. Call this when entering a name-entry scene."""
        self.text_buffer = initial
        self.text_submit = False
        self.text_cancel = False

    # ------------------------------------------------------------------
    def _poll_pad_axes(self) -> None:
        """Read sticks + triggers each frame to update held + edge state."""
        if self._joy is None:
            self._pad_left = False
            self._pad_right = False
            self._pad_down = False
            return

        try:
            ax = self._joy.get_axis(AXIS_LX)
            ay = self._joy.get_axis(AXIS_LY)
        except Exception:
            ax = 0.0
            ay = 0.0

        stick_left = ax < -STICK_DEADZONE
        stick_right = ax > STICK_DEADZONE
        stick_down = ay > STICK_DEADZONE

        self._pad_left = stick_left or self._hat_left
        self._pad_right = stick_right or self._hat_right
        self._pad_down = stick_down or self._hat_down

        # Triggers as analog dash buttons. Fire dash on the rising edge.
        try:
            lt = self._joy.get_axis(AXIS_LT)
        except Exception:
            lt = -1.0
        try:
            rt = self._joy.get_axis(AXIS_RT)
        except Exception:
            rt = -1.0
        pulled = (lt > TRIGGER_THRESHOLD) or (rt > TRIGGER_THRESHOLD)
        if pulled and not self._trigger_held:
            self.dash_pressed = True
        self._trigger_held = pulled

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event) -> None:
        if ev.type == pygame.QUIT:
            self.quit_pressed = True
            return
        # Pad hot-plug.
        if ev.type == pygame.JOYDEVICEADDED:
            self._init_joystick()
            return
        if ev.type == pygame.JOYDEVICEREMOVED:
            try:
                if self._joy is not None:
                    self._joy.quit()
            except Exception:
                pass
            self._joy = None
            self._joy_present = False
            self._pad_left = self._pad_right = self._pad_down = False
            self._hat_left = self._hat_right = self._hat_down = False
            return
        # Pad events work in BOTH gameplay and text-input modes (we don't
        # accept text from a pad, but A/B/Start should still navigate).
        if ev.type in (
            pygame.JOYBUTTONDOWN,
            pygame.JOYBUTTONUP,
            pygame.JOYHATMOTION,
        ):
            self._handle_pad_event(ev)
            return
        # Text-input mode short-circuits gameplay key bindings.
        if self.text_mode and ev.type == pygame.KEYDOWN:
            self._handle_text_keydown(ev)
            return
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k in (pygame.K_LEFT, pygame.K_a):
                self._kb_left = True
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self._kb_right = True
            elif k in (pygame.K_DOWN, pygame.K_s):
                self._kb_down = True
            elif k in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                self.jump_pressed = True
                self.start_pressed = True
            elif k in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_x):
                self.dash_pressed = True
            elif k in (pygame.K_e, pygame.K_f, pygame.K_z):
                self.bomb_pressed = True
            elif k == pygame.K_r:
                self.restart_pressed = True
            elif k == pygame.K_RETURN:
                self.start_pressed = True
            elif k == pygame.K_m:
                self.mute_music_pressed = True
            elif k == pygame.K_n:
                self.mute_sfx_pressed = True
            elif k == pygame.K_p:
                self.rename_pressed = True
            elif k == pygame.K_ESCAPE:
                self.quit_pressed = True
        elif ev.type == pygame.KEYUP:
            k = ev.key
            if k in (pygame.K_LEFT, pygame.K_a):
                self._kb_left = False
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self._kb_right = False
            elif k in (pygame.K_DOWN, pygame.K_s):
                self._kb_down = False
            elif k in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                self.jump_released = True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            sx, sy = ev.pos
            self.click_xy = (sx // self._render_scale, sy // self._render_scale)

    # ------------------------------------------------------------------
    def _handle_pad_event(self, ev: pygame.event.Event) -> None:
        """Translate gamepad button + d-pad events into the same flags
        produced by the keyboard path."""
        if ev.type == pygame.JOYHATMOTION:
            # value is (x, y) where +1 right, +1 up
            hx, hy = ev.value
            self._hat_left = hx < 0
            self._hat_right = hx > 0
            self._hat_down = hy < 0
            return

        if ev.type == pygame.JOYBUTTONDOWN:
            b = ev.button
            if b == BTN_A:
                # A jumps in gameplay AND confirms in menus / text mode.
                self.jump_pressed = True
                self.start_pressed = True
                if self.text_mode:
                    self.text_submit = True
            elif b == BTN_B:
                # B cancels text entry. We deliberately don't bind it to
                # restart so an accidental bump mid-run can't abort the
                # player's progress; A or Start handles restart on the
                # death/title screens.
                if self.text_mode:
                    self.text_cancel = True
            elif b == BTN_X:
                self.bomb_pressed = True
            elif b == BTN_Y:
                self.mute_music_pressed = True
            elif b in (BTN_LB, BTN_RB):
                self.dash_pressed = True
            elif b == BTN_BACK:
                self.mute_sfx_pressed = True
            elif b == BTN_START:
                # Start = confirm on menus / restart on death. Same logic
                # as the A button: gameplay code reads start_pressed only
                # on TITLE/DEAD, so this can't abort an active run.
                self.start_pressed = True
            return

        if ev.type == pygame.JOYBUTTONUP:
            b = ev.button
            if b == BTN_A:
                # Mirrors keyboard SPACE-up: ends a variable-height jump.
                self.jump_released = True
            return

    # ------------------------------------------------------------------
    def _handle_text_keydown(self, ev: pygame.event.Event) -> None:
        k = ev.key
        if k == pygame.K_RETURN or k == pygame.K_KP_ENTER:
            self.text_submit = True
            return
        if k == pygame.K_ESCAPE:
            self.text_cancel = True
            return
        if k == pygame.K_BACKSPACE:
            if self.text_buffer:
                self.text_buffer = self.text_buffer[:-1]
            return
        # Append printable characters from ev.unicode.
        ch = getattr(ev, "unicode", "") or ""
        if ch and ch.isprintable() and ch != "\t":
            self.text_buffer += ch
