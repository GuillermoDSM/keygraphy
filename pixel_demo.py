#!/usr/bin/env python3
"""Animated pixel-art renderer for Keygraphy terminals.

This is an isolated rendering experiment. It does not import the main
application, so it can evolve independently before becoming an optional
frontend. The scene uses a logical pixel buffer and maps two vertical pixels
to one terminal cell with Unicode half blocks. A separate Braille layer shows
that higher-density terminal rendering can coexist with the main scene.

Run it with:

    python3 pixel_demo.py
    python3 pixel_demo.py --snapshot --plain

Press q or Escape to quit, Space to pause, r to reseed the particles, and m
to cycle the color mode. Use --snapshot when launching from an IDE output
panel or another environment without an interactive terminal. Windows users
should run the animation in Windows Terminal.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
import random
import re
import select
import shutil
import sys
import time
from typing import Iterator


Color = tuple[int, int, int]
BLACK: Color = (0, 0, 0)
WHITE: Color = (245, 249, 255)
CYAN: Color = (55, 235, 255)
MAGENTA: Color = (241, 75, 255)
GOLD: Color = (255, 191, 70)
BLUE: Color = (74, 117, 255)
VIOLET: Color = (137, 83, 255)
GREEN: Color = (94, 255, 174)

RESET = "\x1b[0m"
CLEAR = "\x1b[2J\x1b[H"
HOME = "\x1b[H"
ERASE_LINE = "\x1b[2K"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"

USE_COLOR = True
USE_TRUECOLOR = True
USE_UNICODE = True

ANSI_PALETTE: tuple[Color, ...] = (
    (0, 0, 0),
    (205, 49, 49),
    (13, 188, 121),
    (229, 229, 16),
    (36, 114, 200),
    (188, 63, 188),
    (17, 168, 205),
    (229, 229, 229),
    (102, 102, 102),
    (241, 76, 76),
    (35, 209, 139),
    (245, 245, 67),
    (59, 142, 234),
    (214, 112, 214),
    (41, 184, 219),
    (255, 255, 255),
)
ANSI_FOREGROUND_CODES = tuple(range(30, 38)) + tuple(range(90, 98))
ANSI_BACKGROUND_CODES = tuple(range(40, 48)) + tuple(range(100, 108))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def mix(first: Color, second: Color, amount: float) -> Color:
    amount = clamp(amount)
    return tuple(
        round(left + (right - left) * amount)
        for left, right in zip(first, second)
    )  # type: ignore[return-value]


def dim(color: Color, amount: float) -> Color:
    return mix(BLACK, color, amount)


def hsv(hue: float, saturation: float = 0.85, value: float = 1.0) -> Color:
    """Return an RGB color without bringing in a color library."""

    hue = (hue % 1.0) * 6.0
    section = int(hue)
    fraction = hue - section
    low = round(value * (1.0 - saturation) * 255)
    middle = round(value * (1.0 - saturation * fraction) * 255)
    high = round(value * 255)
    middle_high = round(value * (1.0 - saturation * (1.0 - fraction)) * 255)
    colors = (
        (high, middle_high, low),
        (middle, high, low),
        (low, high, middle_high),
        (low, middle, high),
        (middle_high, low, high),
        (high, low, middle),
    )
    return colors[section]


def terminal_supports_controls() -> bool:
    term = os.environ.get("TERM", "").lower()
    return os.name == "nt" or term not in {"", "dumb", "unknown"}


def configure_output(plain: bool = False) -> None:
    global USE_COLOR, USE_TRUECOLOR, USE_UNICODE
    term = os.environ.get("TERM", "").lower()
    color_term = os.environ.get("COLORTERM", "").lower()
    encoding = (sys.stdout.encoding or "").lower()
    USE_UNICODE = "utf" in encoding or "65001" in encoding
    USE_COLOR = not plain and "NO_COLOR" not in os.environ and term not in {
        "",
        "dumb",
        "unknown",
    }
    USE_TRUECOLOR = USE_COLOR and color_term in {"truecolor", "24bit"}


def nearest_ansi_color(color: Color) -> int:
    return min(
        range(len(ANSI_PALETTE)),
        key=lambda index: sum(
            (channel - palette_channel) ** 2
            for channel, palette_channel in zip(color, ANSI_PALETTE[index])
        ),
    )


def foreground(color: Color) -> str:
    if not USE_COLOR:
        return ""
    if not USE_TRUECOLOR:
        return f"\x1b[{ANSI_FOREGROUND_CODES[nearest_ansi_color(color)]}m"
    red, green, blue = color
    return f"\x1b[38;2;{red};{green};{blue}m"


def background(color: Color) -> str:
    if not USE_COLOR:
        return ""
    if not USE_TRUECOLOR:
        return f"\x1b[{ANSI_BACKGROUND_CODES[nearest_ansi_color(color)]}m"
    red, green, blue = color
    return f"\x1b[48;2;{red};{green};{blue}m"


def styled(text: str, color: Color, bold: bool = False) -> str:
    if not USE_COLOR:
        return text
    prefix = "\x1b[1m" if bold else ""
    return f"{prefix}{foreground(color)}{text}{RESET}"


class PixelCanvas:
    """Small RGBA-like logical canvas backed by RGB pixels."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.pixels: list[Color | None] = [None] * (width * height)

    def clear(self) -> None:
        self.pixels[:] = [None] * len(self.pixels)

    def _index(self, x: int, y: int) -> int | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            return y * self.width + x
        return None

    def put(self, x: int, y: int, color: Color, opacity: float = 1.0) -> None:
        index = self._index(x, y)
        if index is None or opacity <= 0:
            return
        if opacity >= 1 or self.pixels[index] is None:
            self.pixels[index] = color
            return
        self.pixels[index] = mix(self.pixels[index] or BLACK, color, opacity)

    def glow(
        self,
        x: int,
        y: int,
        color: Color,
        radius: int = 2,
        opacity: float = 0.35,
    ) -> None:
        for offset_y in range(-radius, radius + 1):
            for offset_x in range(-radius, radius + 1):
                distance = math.hypot(offset_x, offset_y)
                if distance > radius:
                    continue
                strength = opacity * (1.0 - distance / (radius + 1))
                self.put(x + offset_x, y + offset_y, color, strength)

    def line(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        color: Color,
        opacity: float = 1.0,
    ) -> None:
        distance = max(abs(end_x - start_x), abs(end_y - start_y), 1)
        steps = int(distance * 1.5)
        for step in range(steps + 1):
            progress = step / steps
            x = round(start_x + (end_x - start_x) * progress)
            y = round(start_y + (end_y - start_y) * progress)
            self.put(x, y, color, opacity)

    def rectangle(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Color,
        opacity: float = 1.0,
        filled: bool = False,
    ) -> None:
        if filled:
            for row in range(y, y + height):
                for column in range(x, x + width):
                    self.put(column, row, color, opacity)
            return
        for column in range(x, x + width):
            self.put(column, y, color, opacity)
            self.put(column, y + height - 1, color, opacity)
        for row in range(y, y + height):
            self.put(x, row, color, opacity)
            self.put(x + width - 1, row, color, opacity)


FONT: dict[str, tuple[str, ...]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "N": ("10001", "11001", "10101", "10101", "10011", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
}


def draw_glyph(
    canvas: PixelCanvas,
    letter: str,
    x: int,
    y: int,
    color: Color,
    scale: int = 1,
    glow: bool = False,
    glow_color: Color | None = None,
    scanline: int | None = None,
) -> None:
    glyph = FONT.get(letter.upper())
    if glyph is None:
        return
    for row, glyph_row in enumerate(glyph):
        for column, value in enumerate(glyph_row):
            if value != "1":
                continue
            pixel_x = x + column * scale
            pixel_y = y + row * scale
            pixel_color = color
            if scanline is not None and pixel_y <= scanline < pixel_y + scale:
                pixel_color = WHITE
            if glow:
                canvas.glow(
                    pixel_x,
                    pixel_y,
                    glow_color or pixel_color,
                    radius=max(2, scale),
                    opacity=0.4,
                )
            for offset_y in range(scale):
                for offset_x in range(scale):
                    canvas.put(pixel_x + offset_x, pixel_y + offset_y, pixel_color)


def draw_pixel_text(
    canvas: PixelCanvas,
    text: str,
    x: int,
    y: int,
    color: Color,
    scale: int,
    scanline: int | None = None,
    glow: bool = True,
    glow_color: Color | None = None,
) -> int:
    cursor = x
    for letter in text:
        if letter == " ":
            cursor += 4 * scale
            continue
        draw_glyph(
            canvas,
            letter,
            cursor,
            y,
            color,
            scale,
            glow=glow,
            glow_color=glow_color,
            scanline=scanline,
        )
        cursor += 6 * scale
    return cursor - x - scale


@dataclass
class Particle:
    x: float
    y: float
    previous_x: float
    previous_y: float
    velocity_x: float
    velocity_y: float
    life: float
    max_life: float
    hue: float


class Scene:
    """State and animation logic independent from the terminal renderer."""

    PALETTES: tuple[tuple[Color, Color, Color], ...] = (
        (CYAN, MAGENTA, GOLD),
        (GREEN, CYAN, BLUE),
        (GOLD, MAGENTA, VIOLET),
    )

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)
        self.time = 0.0
        self.mode = 0
        self.paused = False
        self.particles: list[Particle] = []
        self._particle_width = 0
        self._particle_height = 0

    def reset_particles(self, width: int, height: int) -> None:
        self._particle_width = width
        self._particle_height = height
        self.particles.clear()
        for _ in range(max(40, width // 2)):
            self.particles.append(self._new_particle(width, height, anywhere=True))

    def _new_particle(self, width: int, height: int, anywhere: bool = False) -> Particle:
        x = self.random.uniform(2, max(3, width - 3))
        y = (
            self.random.uniform(1, max(2, height - 12))
            if anywhere
            else self.random.uniform(height * 0.35, max(2, height - 12))
        )
        velocity_x = self.random.uniform(-5.0, 5.0)
        velocity_y = self.random.uniform(-3.0, 1.5)
        life = self.random.uniform(1.5, 5.0)
        return Particle(x, y, x, y, velocity_x, velocity_y, life, life, self.random.random())

    def update(self, delta: float, width: int, height: int) -> None:
        self.time += delta
        if width != self._particle_width or height != self._particle_height:
            self.reset_particles(width, height)
        for index, particle in enumerate(self.particles):
            particle.previous_x = particle.x
            particle.previous_y = particle.y
            particle.x += particle.velocity_x * delta
            particle.y += particle.velocity_y * delta
            particle.velocity_y += math.sin(self.time * 1.2 + index) * delta * 0.8
            particle.life -= delta
            if (
                particle.life <= 0
                or particle.x < -3
                or particle.x >= width + 3
                or particle.y < -3
                or particle.y >= height - 8
            ):
                self.particles[index] = self._new_particle(width, height)

    def palette(self) -> tuple[Color, Color, Color]:
        return self.PALETTES[self.mode % len(self.PALETTES)]

    def cycle_mode(self) -> None:
        self.mode = (self.mode + 1) % len(self.PALETTES)

    def reseed(self, width: int, height: int) -> None:
        self.random.seed(int(self.time * 1000) ^ width ^ (height << 4))
        self.reset_particles(width, height)


BRAILLE_DOTS = (
    (0, 0, 0x01),
    (0, 1, 0x02),
    (0, 2, 0x04),
    (1, 0, 0x08),
    (1, 1, 0x10),
    (1, 2, 0x20),
    (0, 3, 0x40),
    (1, 3, 0x80),
)


class BrailleCanvas:
    """Dense 2x4-dot canvas used for the animated telemetry strip."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.bits = [0] * (width * height)
        self.colors: list[Color | None] = [None] * (width * height)

    def dot(self, x: int, y: int, color: Color) -> None:
        if not (0 <= x < self.width * 2 and 0 <= y < self.height * 4):
            return
        cell_x, dot_x = divmod(x, 2)
        cell_y, dot_y = divmod(y, 4)
        for offset_x, offset_y, bit in BRAILLE_DOTS:
            if dot_x == offset_x and dot_y == offset_y:
                index = cell_y * self.width + cell_x
                self.bits[index] |= bit
                self.colors[index] = color
                return

    def render(self) -> list[str]:
        lines: list[str] = []
        for row in range(self.height):
            chunks: list[str] = []
            for column in range(self.width):
                index = row * self.width + column
                if not self.bits[index]:
                    chunks.append(" ")
                elif not USE_UNICODE:
                    chunks.append("*")
                else:
                    color = self.colors[index] or WHITE
                    chunks.append(
                        f"{foreground(color)}{chr(0x2800 + self.bits[index])}{RESET}"
                    )
            lines.append(ERASE_LINE + "".join(chunks) + RESET)
        return lines


def draw_braille_strip(width: int, scene: Scene) -> list[str]:
    strip = BrailleCanvas(width, 2)
    first, second, accent = scene.palette()
    logical_width = width * 2
    for x in range(logical_width):
        normalized = x / max(1, logical_width - 1)
        wave = math.sin(normalized * 18.0 + scene.time * 5.0)
        wave += 0.4 * math.sin(normalized * 43.0 - scene.time * 2.0)
        y = round(3.5 + wave * 2.0)
        color = mix(first, second, normalized)
        strip.dot(x, y, color)
        if x % 7 == 0:
            strip.dot(x, max(0, y - 1), accent)
    for index in range(8):
        x = round((math.sin(scene.time * 0.8 + index * 2.7) * 0.5 + 0.5) * (logical_width - 1))
        y = round((math.cos(scene.time * 1.1 + index) * 0.5 + 0.5) * 7)
        strip.dot(x, y, mix(second, accent, index / 8))
    return strip.render()


def draw_orbit(canvas: PixelCanvas, center_x: float, center_y: float, scene: Scene) -> None:
    first, second, accent = scene.palette()
    for ring_index, radius in enumerate((13, 18, 24)):
        if radius > canvas.width // 2 - 2:
            continue
        start = scene.time * (0.55 + ring_index * 0.16) * (-1 if ring_index % 2 else 1)
        for step in range(120):
            angle = start + step / 120 * math.tau
            wobble = math.sin(angle * 3 + scene.time * 2 + ring_index) * 1.2
            x = round(center_x + math.cos(angle) * (radius + wobble))
            y = round(center_y + math.sin(angle) * (radius + wobble) * 0.55)
            color = mix(first, second, step / 120)
            opacity = 0.18 + 0.25 * (0.5 + 0.5 * math.sin(angle * 2 - scene.time * 3))
            canvas.put(x, y, color, opacity)
        angle = start + scene.time * 0.5
        head_x = round(center_x + math.cos(angle) * radius)
        head_y = round(center_y + math.sin(angle) * radius * 0.55)
        canvas.glow(head_x, head_y, accent, radius=3, opacity=0.8)
        canvas.put(head_x, head_y, WHITE)


def draw_particles(canvas: PixelCanvas, scene: Scene) -> None:
    first, second, _ = scene.palette()
    for index, particle in enumerate(scene.particles):
        life = clamp(particle.life / particle.max_life)
        color = mix(first, second, particle.hue)
        canvas.line(
            particle.previous_x,
            particle.previous_y,
            particle.x,
            particle.y,
            color,
            opacity=0.18 * life,
        )
        canvas.glow(round(particle.x), round(particle.y), color, radius=1, opacity=0.35 * life)
        canvas.put(round(particle.x), round(particle.y), mix(color, WHITE, 0.35), life)
        if index % 13 == 0:
            canvas.put(round(particle.x) + 1, round(particle.y), WHITE, life * 0.7)


def draw_wave(canvas: PixelCanvas, scene: Scene, y: int) -> None:
    first, second, accent = scene.palette()
    for x in range(canvas.width):
        normalized = x / max(1, canvas.width - 1)
        wave = math.sin(normalized * 13 + scene.time * 3.2)
        wave += math.sin(normalized * 31 - scene.time * 2.1) * 0.35
        wave += math.sin(normalized * 67 + scene.time * 4.9) * 0.14
        offset = round(wave * 2.4)
        color = mix(first, second, normalized)
        canvas.put(x, y + offset, color, 0.8)
        canvas.put(x, y + offset + 1, accent, 0.28)
        if x % 9 == 0:
            canvas.glow(x, y + offset, color, radius=2, opacity=0.45)


def draw_bars(canvas: PixelCanvas, scene: Scene, y: int) -> None:
    first, second, _ = scene.palette()
    bar_count = min(8, max(4, canvas.width // 16))
    for index in range(bar_count):
        phase = scene.time * (2.4 + index * 0.13) + index * 1.9
        height = 3 + round((math.sin(phase) * 0.5 + 0.5) * 7)
        color = mix(first, second, index / max(1, bar_count - 1))
        x_left = 2 + index * 2
        x_right = canvas.width - 3 - index * 2
        for offset in range(height):
            opacity = 0.18 + offset / max(1, height) * 0.65
            canvas.put(x_left, y - offset, color, opacity)
            canvas.put(x_right, y - offset, color, opacity)


def draw_keycaps(canvas: PixelCanvas, scene: Scene) -> None:
    keys = "EASONIRL"
    key_width = 7 if canvas.width >= 78 else 5
    gap = 2 if canvas.width >= 78 else 1
    total_width = len(keys) * key_width + (len(keys) - 1) * gap
    start_x = max(0, (canvas.width - total_width) // 2)
    top = canvas.height - 10
    focused = int(scene.time * 1.7) % len(keys)
    first, second, accent = scene.palette()
    for index, letter in enumerate(keys):
        x = start_x + index * (key_width + gap)
        is_focused = index == focused
        pulse = 0.5 + 0.5 * math.sin(scene.time * 5.0 - index * 0.7)
        fill = mix(BLACK, first if index % 2 == 0 else second, 0.22 + pulse * 0.08)
        if is_focused:
            fill = mix(fill, accent, 0.45 + pulse * 0.25)
            canvas.glow(x + 3, top + 3, accent, radius=4, opacity=0.35 + pulse * 0.25)
        canvas.rectangle(x, top, key_width, 7, fill, filled=True)
        canvas.rectangle(x, top, key_width, 7, mix(fill, WHITE, 0.55), opacity=0.7)
        draw_glyph(
            canvas,
            letter,
            x + (key_width - 5) // 2,
            top + 0,
            WHITE if is_focused else mix(first, second, index / len(keys)),
            scale=1,
            glow=is_focused,
        )


def draw_scene(canvas: PixelCanvas, scene: Scene) -> None:
    canvas.clear()
    first, second, accent = scene.palette()
    draw_particles(canvas, scene)

    horizon = canvas.height - 14
    for x in range(0, canvas.width, 4):
        canvas.put(x, horizon, mix(first, second, x / max(1, canvas.width)), 0.16)
        for depth in range(1, 4):
            canvas.put(x, horizon + depth * 2, second, 0.04 / depth)
    for row in range(horizon + 1, canvas.height - 11, 3):
        canvas.line(0, row, canvas.width - 1, row, second, 0.025)

    center_x = canvas.width / 2
    center_y = max(12, min(horizon - 13, canvas.height * 0.37))
    draw_orbit(canvas, center_x, center_y, scene)

    logo = "KEYGRAPHY"
    scale = 2 if canvas.width >= 108 and canvas.height >= 36 else 1
    logo_width = len(logo) * 6 * scale - scale
    logo_x = round(center_x - logo_width / 2)
    logo_y = round(center_y - 4 * scale)
    scanline = round(logo_y + (math.sin(scene.time * 1.3) * 0.5 + 0.5) * 7 * scale)
    plate_x = logo_x - 2
    plate_y = logo_y - 2
    plate_width = logo_width + 4
    plate_height = 7 * scale + 4
    canvas.rectangle(plate_x, plate_y, plate_width, plate_height, BLACK, filled=True)
    canvas.rectangle(
        plate_x,
        plate_y,
        plate_width,
        plate_height,
        dim(first, 0.58),
        opacity=1.0,
    )
    canvas.rectangle(
        plate_x + 1,
        plate_y + 1,
        plate_width - 2,
        plate_height - 2,
        BLACK,
        filled=True,
    )
    draw_pixel_text(
        canvas,
        logo,
        logo_x,
        logo_y,
        first,
        scale,
        scanline,
        glow=True,
        glow_color=first,
    )
    draw_pixel_text(
        canvas,
        logo,
        logo_x,
        logo_y,
        WHITE,
        scale,
        scanline,
        glow=False,
    )

    pulse_radius = 4 + round((math.sin(scene.time * 2.0) * 0.5 + 0.5) * 5)
    for angle_index in range(32):
        angle = scene.time * 0.8 + angle_index / 32 * math.tau
        x = round(center_x + math.cos(angle) * pulse_radius)
        y = round(center_y + math.sin(angle) * pulse_radius * 0.55)
        canvas.put(x, y, accent, 0.7)

    draw_bars(canvas, scene, max(8, horizon - 2))
    draw_wave(canvas, scene, horizon - 5)
    draw_keycaps(canvas, scene)


def render_halfblocks(canvas: PixelCanvas) -> list[str]:
    """Map two logical vertical pixels to one terminal cell."""

    lines: list[str] = []
    for row in range(0, canvas.height, 2):
        chunks: list[str] = []
        for column in range(canvas.width):
            top = canvas.pixels[row * canvas.width + column]
            bottom = (
                canvas.pixels[(row + 1) * canvas.width + column]
                if row + 1 < canvas.height
                else None
            )
            if not USE_COLOR:
                if top == BLACK:
                    top = None
                if bottom == BLACK:
                    bottom = None
            if top is None and bottom is None:
                chunks.append(" ")
            elif bottom is None:
                glyph = "▀" if USE_UNICODE else "#"
                chunks.append(f"{foreground(top or BLACK)}{glyph}{RESET}")
            elif top is None:
                glyph = "▄" if USE_UNICODE else "#"
                chunks.append(f"{foreground(bottom)}{glyph}{RESET}")
            else:
                glyph = "▀" if USE_UNICODE else "#"
                chunks.append(
                    f"{foreground(top)}{background(bottom)}{glyph}{RESET}"
                )
        lines.append(ERASE_LINE + "".join(chunks) + RESET)
    return lines


def fit_text(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    ellipsis = "…" if USE_UNICODE else "..."
    return text[: max(0, width - len(ellipsis))] + ellipsis


ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def without_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text).replace("\r\n", "\n")


def render_frame(
    width: int,
    height: int,
    scene: Scene,
    fps: float,
) -> str:
    if width < 60 or height < 18:
        message = "KEYGRAPHY PIXEL LAB necesita una terminal de al menos 60x18"
        return HOME + ERASE_LINE + styled(message[:width], GOLD, bold=True) + "\r\n" + "\x1b[J"

    main_rows = height - 5
    canvas = PixelCanvas(width, main_rows * 2)
    draw_scene(canvas, scene)
    first, second, accent = scene.palette()
    mode = f"MODE {scene.mode + 1}/{len(Scene.PALETTES)}"
    status = "PAUSED" if scene.paused else f"{fps:02.0f} FPS"
    header = fit_text(
        f"  KEYGRAPHY // PIXEL LAB     {mode}     {status}",
        width,
    )
    footer = fit_text(
        "  ADAPTIVE PRACTICE  |  [E A S O N I R L]  |  FOCUS LOCKED",
        width,
    )
    controls = fit_text("  q/esc exit   space pause   m palette   r reseed", width)

    lines = [
        ERASE_LINE + styled(header, first, bold=True),
        *draw_braille_strip(width, scene),
        *render_halfblocks(canvas),
        ERASE_LINE + styled(footer, second),
        ERASE_LINE + styled(controls, accent),
    ]
    return HOME + "\r\n".join(lines) + RESET + "\x1b[J"


@contextmanager
def raw_terminal() -> Iterator[None]:
    if os.name == "nt":
        yield
        return

    import termios
    import tty

    file_descriptor = sys.stdin.fileno()
    original = termios.tcgetattr(file_descriptor)
    try:
        tty.setcbreak(file_descriptor)
        yield
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, original)


def enable_windows_vt() -> tuple[object, int] | None:
    if os.name != "nt":
        return None
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_uint()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return None
    original = mode.value
    if not kernel32.SetConsoleMode(handle, original | 0x0004):
        return None
    return handle, original


def restore_windows_vt(state: tuple[object, int] | None) -> None:
    if state is None:
        return
    import ctypes

    ctypes.windll.kernel32.SetConsoleMode(state[0], state[1])


def read_key() -> str | None:
    if os.name == "nt":
        import msvcrt

        if not msvcrt.kbhit():
            return None
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            msvcrt.getwch()
            return None
        return key

    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return None
    # Avoid TextIOWrapper prefetching queued keys after select reports readiness.
    encoding = sys.stdin.encoding or "utf-8"
    return os.read(sys.stdin.fileno(), 1).decode(encoding, errors="replace")


def run(fps: int, max_frames: int = 0) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        snapshot(plain=True)
        return
    if not terminal_supports_controls():
        snapshot(plain=True)
        return

    configure_output()
    fps = max(10, min(60, fps))
    frame_duration = 1.0 / fps
    scene = Scene()
    vt_state = enable_windows_vt()
    sys.stdout.write(HIDE_CURSOR + CLEAR)
    sys.stdout.flush()
    last_time = time.monotonic()
    frame_count = 0
    measured_fps = float(fps)
    try:
        with raw_terminal():
            while True:
                frame_started = time.monotonic()
                delta = min(0.1, frame_started - last_time)
                last_time = frame_started
                width, height = shutil.get_terminal_size((80, 24))
                main_height = max(1, (height - 5) * 2)
                if delta > 0.005:
                    measured_fps = measured_fps * 0.9 + (1.0 / delta) * 0.1
                if not scene.paused:
                    scene.update(delta, width, main_height)
                key = read_key()
                if key is not None:
                    lowered = key.lower()
                    if key in ("\x03", "\x1b") or lowered == "q":
                        break
                    if key == " ":
                        scene.paused = not scene.paused
                    elif lowered == "m":
                        scene.cycle_mode()
                    elif lowered == "r":
                        scene.reseed(width, main_height)

                sys.stdout.write(render_frame(width, height, scene, measured_fps))
                sys.stdout.flush()
                frame_count += 1
                if max_frames and frame_count >= max_frames:
                    break
                time.sleep(max(0.0, frame_duration - (time.monotonic() - frame_started)))
    finally:
        sys.stdout.write(RESET + SHOW_CURSOR + "\r\n")
        sys.stdout.flush()
        restore_windows_vt(vt_state)


def snapshot(plain: bool = False) -> None:
    """Render one frame without requiring an interactive terminal."""

    plain = plain or not terminal_supports_controls()
    configure_output(plain)
    width, height = shutil.get_terminal_size((80, 24))
    scene = Scene(seed=7)
    scene.update(1 / 30, width, max(1, (height - 5) * 2))
    frame = render_frame(width, height, scene, 30.0)
    if plain:
        frame = without_ansi(frame)
    sys.stdout.write(frame.rstrip("\n") + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fps", type=int, default=30, help="límite de cuadros por segundo")
    parser.add_argument(
        "--frames",
        type=int,
        default=0,
        help="termina después de N cuadros; útil para pruebas manuales",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="renderiza un cuadro sin necesitar una terminal interactiva",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="quita colores y secuencias ANSI; se usa con --snapshot",
    )
    args = parser.parse_args()
    if args.snapshot:
        snapshot(args.plain)
        return 0
    if args.plain:
        parser.error("--plain solo se puede usar junto con --snapshot")
    try:
        run(args.fps, args.frames)
    except (KeyboardInterrupt, RuntimeError) as error:
        print(f"pixel_demo: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
