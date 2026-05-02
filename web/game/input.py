"""Keyboard input mapping for the endless runner."""
from __future__ import annotations
import pygame


class Input:
    def __init__(self) -> None:
        # Held states.
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

    def begin_frame(self) -> None:
        self.jump_pressed = False
        self.jump_released = False
        self.dash_pressed = False
        self.bomb_pressed = False
        self.restart_pressed = False
        self.start_pressed = False

    def handle_event(self, ev: pygame.event.Event) -> None:
        if ev.type == pygame.QUIT:
            self.quit_pressed = True
            return
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k in (pygame.K_LEFT, pygame.K_a):
                self.left = True
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.right = True
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.down = True
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
            elif k == pygame.K_ESCAPE:
                self.quit_pressed = True
        elif ev.type == pygame.KEYUP:
            k = ev.key
            if k in (pygame.K_LEFT, pygame.K_a):
                self.left = False
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.right = False
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.down = False
            elif k in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                self.jump_released = True
