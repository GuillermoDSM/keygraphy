#!/usr/bin/env python3
"""Numbered speed-themed pixel animation gallery for Keygraphy.

This gallery reuses the portable renderer from ``pixel_demo.py``. It is an
idea board for choosing a visual language before integrating one scene into
the real application.

Run it from a real terminal with:

    python3 pixel_gallery.py

Controls:

    n / p       next / previous example
    1..9 / 0     choose an item on the current catalog page
    g            open or close the numbered catalog
    m            change the color palette
    space        pause
    r            reseed particles
    q / Escape   quit
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import random
import shutil
import sys
import time
from typing import Callable

import pixel_demo as renderer


Color = renderer.Color
BLACK = renderer.BLACK
WHITE = renderer.WHITE
CYAN = renderer.CYAN
MAGENTA = renderer.MAGENTA
GOLD = renderer.GOLD
BLUE = renderer.BLUE
VIOLET = renderer.VIOLET
GREEN = renderer.GREEN
HOME = renderer.HOME
ERASE_LINE = renderer.ERASE_LINE
RESET = renderer.RESET
HIDE_CURSOR = renderer.HIDE_CURSOR
SHOW_CURSOR = renderer.SHOW_CURSOR


class GalleryState(renderer.Scene):
    def __init__(self, seed: int | None = None) -> None:
        super().__init__(seed)
        self._example = 0
        self.example_started = self.time

    @property
    def example(self) -> int:
        return self._example

    @example.setter
    def example(self, value: int) -> None:
        if value != self._example:
            self.example_started = self.time
        self._example = value


@dataclass(frozen=True)
class Example:
    title: str
    subtitle: str
    tags: str
    draw: Callable[[renderer.PixelCanvas, GalleryState], None]
    braille: bool = False


def polar(
    center_x: float,
    center_y: float,
    radius: float,
    angle: float,
    y_scale: float = 1.0,
) -> tuple[int, int]:
    return (
        round(center_x + math.cos(angle) * radius),
        round(center_y + math.sin(angle) * radius * y_scale),
    )


def ring(
    canvas: renderer.PixelCanvas,
    center_x: float,
    center_y: float,
    radius: float,
    color: Color,
    opacity: float = 0.7,
    y_scale: float = 0.55,
    phase: float = 0.0,
    segments: int = 120,
) -> None:
    for index in range(segments):
        angle = phase + index / segments * math.tau
        x, y = polar(center_x, center_y, radius, angle, y_scale)
        canvas.put(x, y, color, opacity)


def arc(
    canvas: renderer.PixelCanvas,
    center_x: float,
    center_y: float,
    radius: float,
    start: float,
    sweep: float,
    color: Color,
    opacity: float = 0.8,
    y_scale: float = 0.55,
) -> None:
    segments = max(12, round(abs(sweep) * radius * 1.5))
    for index in range(segments + 1):
        angle = start + sweep * index / segments
        x, y = polar(center_x, center_y, radius, angle, y_scale)
        canvas.put(x, y, color, opacity)


def ray(
    canvas: renderer.PixelCanvas,
    center_x: float,
    center_y: float,
    angle: float,
    length: float,
    color: Color,
    opacity: float = 0.7,
    y_scale: float = 0.55,
) -> None:
    end_x, end_y = polar(center_x, center_y, length, angle, y_scale)
    canvas.line(center_x, center_y, end_x, end_y, color, opacity)


def draw_particles(
    canvas: renderer.PixelCanvas,
    state: GalleryState,
    first: Color,
    second: Color,
    scale: float = 1.0,
) -> None:
    for index, particle in enumerate(state.particles):
        life = renderer.clamp(particle.life / particle.max_life)
        color = renderer.mix(first, second, particle.hue)
        canvas.line(
            particle.previous_x * scale,
            particle.previous_y * scale,
            particle.x * scale,
            particle.y * scale,
            color,
            0.14 * life,
        )
        x = round(particle.x * scale)
        y = round(particle.y * scale)
        canvas.put(x, y, color, 0.35 + life * 0.65)
        if index % 9 == 0:
            canvas.glow(x, y, color, radius=1, opacity=0.32 * life)


def draw_frame(canvas: renderer.PixelCanvas, color: Color, opacity: float = 0.45) -> None:
    if canvas.width < 8 or canvas.height < 8:
        return
    canvas.rectangle(2, 2, canvas.width - 4, canvas.height - 4, color, opacity)
    canvas.put(5, 2, WHITE, 0.7)
    canvas.put(canvas.width - 6, canvas.height - 3, WHITE, 0.7)


def draw_gauge(
    canvas: renderer.PixelCanvas,
    center_x: float,
    center_y: float,
    radius: float,
    value: float,
    color: Color,
    accent: Color,
    label: bool = False,
) -> None:
    start = math.pi * 0.78
    sweep = math.pi * 1.44
    ring(
        canvas,
        center_x,
        center_y,
        radius,
        renderer.dim(color, 0.55),
        0.8,
        y_scale=1.0,
    )
    ring(
        canvas,
        center_x,
        center_y,
        radius - 2,
        renderer.dim(color, 0.22),
        0.7,
        y_scale=1.0,
    )
    for index in range(13):
        amount = index / 12
        angle = start + sweep * amount
        inner = radius - (4 if index % 3 == 0 else 2)
        x1, y1 = polar(center_x, center_y, inner, angle, 1.0)
        x2, y2 = polar(center_x, center_y, radius + 1, angle, 1.0)
        canvas.line(x1, y1, x2, y2, accent if amount <= value else color, 0.75)
    needle_angle = start + sweep * renderer.clamp(value)
    end_x, end_y = polar(center_x, center_y, radius - 5, needle_angle, 1.0)
    canvas.glow(round(end_x), round(end_y), accent, radius=2, opacity=0.8)
    canvas.line(center_x, center_y, end_x, end_y, WHITE, 1.0)
    canvas.put(round(center_x), round(center_y), accent, 1.0)
    if label:
        renderer.draw_pixel_text(
            canvas,
            "GO",
            round(center_x - 5),
            round(center_y + 2),
            accent,
            1,
            glow=False,
        )


def draw_horizon(canvas: renderer.PixelCanvas, state: GalleryState, color: Color) -> None:
    horizon = round(canvas.height * 0.46)
    drift = math.sin(state.time * 1.5) * 2
    for offset in range(-3, 4):
        canvas.line(0, horizon + offset, canvas.width - 1, horizon + offset, color, 0.12)
    for index in range(9):
        y = horizon + round((index + 1) ** 1.55 + drift) * 2
        canvas.line(0, y, canvas.width - 1, y, color, 0.12)
    for x in range(-canvas.width, canvas.width * 2, 9):
        canvas.line(canvas.width // 2, horizon, x, canvas.height, color, 0.16)


def draw_speed_lines(
    canvas: renderer.PixelCanvas,
    state: GalleryState,
    first: Color,
    second: Color,
    count: int = 70,
    center_y: float | None = None,
) -> None:
    center_x = canvas.width / 2
    center_y = center_y if center_y is not None else canvas.height / 2
    for index in range(count):
        phase = (index * 0.618 + state.time * (0.22 + index % 5 * 0.02)) % 1.0
        angle = (index * 2.399 + math.sin(state.time * 0.3 + index) * 0.1) % math.tau
        inner = 3 + phase * max(canvas.width, canvas.height) * 0.35
        outer = inner + 2 + phase * 5
        start_x, start_y = polar(center_x, center_y, inner, angle, 0.58)
        end_x, end_y = polar(center_x, center_y, outer, angle, 0.58)
        color = renderer.mix(first, second, index / max(1, count - 1))
        canvas.line(start_x, start_y, end_x, end_y, color, 0.18 + phase * 0.65)


def draw_flame(
    canvas: renderer.PixelCanvas,
    x: float,
    y: float,
    width: float,
    length: float,
    state: GalleryState,
    hot: Color,
    cool: Color,
) -> None:
    for index in range(26):
        amount = (index / 26 + state.time * 1.8) % 1.0
        drift = math.sin(index * 5.3 + state.time * 8) * width * 0.32
        start_x = x + drift * 0.25
        start_y = y + amount * length
        end_x = x + drift + math.sin(index + state.time * 4) * width * 0.3
        end_y = start_y + 2 + amount * 5
        color = renderer.mix(hot, cool, amount)
        canvas.line(start_x, start_y, end_x, end_y, color, 0.35 + (1 - amount) * 0.6)
        if index % 4 == 0:
            canvas.glow(round(end_x), round(end_y), hot, radius=1, opacity=0.35)


def draw_rocket(
    canvas: renderer.PixelCanvas,
    x: float,
    y: float,
    scale: float,
    state: GalleryState,
    first: Color,
    accent: Color,
) -> None:
    half_width = max(2, round(scale * 2.5))
    nose = round(y - scale * 6)
    base = round(y + scale * 5)
    left = round(x - half_width)
    right = round(x + half_width)
    canvas.line(x, nose, left, base, WHITE, 0.9)
    canvas.line(x, nose, right, base, WHITE, 0.9)
    canvas.line(left, base, right, base, first, 0.9)
    canvas.line(x, nose + scale * 2, x, base - 1, accent, 0.8)
    canvas.line(left, base - scale, left - scale, base + scale, first, 0.75)
    canvas.line(right, base - scale, right + scale, base + scale, first, 0.75)
    draw_flame(canvas, x, base + 1, half_width * 1.8, scale * 8, state, GOLD, accent)


def draw_velocity_core(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, first)
    center_x = canvas.width * 0.5
    center_y = canvas.height * 0.47
    value = math.sin(state.time * 1.4) * 0.5 + 0.5
    draw_gauge(canvas, center_x, center_y, min(canvas.width, canvas.height) * 0.25, value, first, accent, True)
    for index in range(5):
        y = 5 + index * 3
        amount = (math.sin(state.time * 2 + index * 0.7) * 0.5 + 0.5)
        width = round((canvas.width * 0.18) * amount)
        canvas.line(5, y, 5 + width, y, renderer.mix(first, second, index / 5), 0.65)
        canvas.line(canvas.width - 6, y, canvas.width - 6 - width, y, renderer.mix(second, accent, index / 5), 0.65)
    for index in range(8):
        x = round(8 + index * (canvas.width - 16) / 7)
        canvas.put(x, canvas.height - 5, accent if index <= round(value * 7) else first, 0.7)


def draw_braille_overdrive(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    scale = min(canvas.height, canvas.width * 0.5)
    instruments = (
        (0.50, 0.50, 0.38),
        (0.16, 0.30, 0.22),
        (0.84, 0.30, 0.19),
        (0.16, 0.76, 0.14),
        (0.84, 0.76, 0.16),
    )
    start, sweep = math.pi * 0.75, math.pi * 1.5
    for index, (x, y, size) in enumerate(instruments):
        cx, cy, radius = canvas.width * x, canvas.height * y, scale * size
        color = renderer.mix(first, second, index / 4)
        speed = 35 + index * 4.3

        def needle_angle(t: float) -> float:
            elapsed = max(0.0, t - state.example_started)
            ramp = 1 - math.exp(-elapsed * (7 + index * 0.5))
            vibration = 0.009 * math.sin(elapsed * speed + index * 1.7)
            vibration += 0.004 * math.sin(elapsed * speed * 2.1)
            value = ramp * (0.96 + vibration * ramp)
            return start + sweep * value

        ring(canvas, cx, cy, radius, renderer.dim(color, 0.55), y_scale=1.0)
        arc(canvas, cx, cy, radius * 0.88, start, sweep, color, y_scale=1.0)
        arc(canvas, cx, cy, radius * 0.88, start + sweep * 0.8,
            sweep * 0.2, MAGENTA, y_scale=1.0)
        for tick in range(17):
            angle = start + sweep * tick / 16
            inner = radius * (0.67 if tick % 4 == 0 else 0.77)
            tx, ty = polar(cx, cy, inner, angle)
            ex, ey = polar(cx, cy, radius * 0.88, angle)
            canvas.line(tx, ty, ex, ey, accent if tick >= 13 else color)
        # Brief trails follow the initial acceleration and small redline vibration.
        for trail in range(3, -1, -1):
            angle = needle_angle(state.time - trail * 0.018)
            ex, ey = polar(cx, cy, radius * 0.68, angle)
            needle_color = WHITE if trail == 0 else renderer.dim(accent, 0.45 / trail)
            canvas.line(cx, cy, ex, ey, needle_color)
        canvas.put(round(cx), round(cy), WHITE)


def draw_afterburner(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, second)
    center_x = canvas.width / 2
    engine_y = canvas.height * 0.35
    for index in range(5):
        x = center_x - 13 + index * 6
        canvas.rectangle(round(x - 2), round(engine_y - 3), 5, 6, renderer.dim(first, 0.35), filled=True)
        canvas.rectangle(round(x - 2), round(engine_y - 3), 5, 6, first, opacity=0.7)
        draw_flame(canvas, x, engine_y + 3, 3 + index % 2, canvas.height * 0.55, state, GOLD, accent)
    for index in range(24):
        angle = math.sin(index * 2.4 + state.time * 4) * 0.25
        ray(canvas, center_x, engine_y + 5, math.pi / 2 + angle, 8 + index * 0.7, renderer.mix(second, accent, index / 24), 0.22)


def draw_warp_tunnel(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, first)
    center_x = canvas.width / 2
    center_y = canvas.height * 0.45
    for index in range(16):
        phase = (index / 16 + state.time * 0.24) % 1.0
        width = 5 + phase * (canvas.width * 0.82)
        height = 3 + phase * (canvas.height * 0.72)
        x = round(center_x - width / 2)
        y = round(center_y - height / 2)
        color = renderer.mix(first, second, phase)
        canvas.rectangle(x, y, round(width), round(height), color, 0.22 + phase * 0.55)
    draw_speed_lines(canvas, state, accent, first, 55, center_y)
    canvas.glow(round(center_x), round(center_y), WHITE, radius=3, opacity=0.55)


def draw_rocket_launch(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, accent)
    lift = (state.time * 3.5) % (canvas.height + 20)
    rocket_y = canvas.height + 8 - lift
    draw_rocket(canvas, canvas.width * 0.5, rocket_y, 1.25, state, first, accent)
    for index in range(22):
        x = (index * 17 + round(state.time * 8)) % max(1, canvas.width)
        y = (index * 13 + round(state.time * 17)) % max(1, canvas.height)
        canvas.put(x, y, renderer.mix(second, accent, index / 22), 0.25)
    for x in range(4, canvas.width, 8):
        canvas.line(x, canvas.height - 3, x + math.sin(state.time + x) * 2, canvas.height - 7, first, 0.16)


def draw_orbital_radar(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, first)
    cx, cy = canvas.width / 2, canvas.height * 0.5
    max_radius = min(canvas.width * 0.42, canvas.height * 0.72)
    for multiplier in (0.35, 0.65, 1.0):
        ring(canvas, cx, cy, max_radius * multiplier, renderer.dim(first, 0.45), 0.65)
    for angle_index in range(10):
        angle = angle_index / 10 * math.tau
        ray(canvas, cx, cy, angle, max_radius, first, 0.22)
    sweep = state.time * 1.4
    for offset in range(8):
        angle = sweep - offset * 0.035
        ray(canvas, cx, cy, angle, max_radius, renderer.mix(accent, first, offset / 8), 0.35 - offset * 0.03)
    for index in range(9):
        angle = index * 2.21
        radius = max_radius * (0.25 + (index % 5) * 0.13)
        x, y = polar(cx, cy, radius, angle)
        if math.sin(sweep - angle) > 0.1:
            canvas.glow(x, y, accent, radius=2, opacity=0.7)
        canvas.put(x, y, WHITE if index % 3 == 0 else second, 0.9)


def draw_hyperdrive_grid(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, second)
    horizon = round(canvas.height * 0.43)
    vanishing_x = canvas.width / 2 + math.sin(state.time * 0.7) * 4
    for index in range(-12, 13):
        bottom_x = vanishing_x + index * 8
        canvas.line(vanishing_x, horizon, bottom_x, canvas.height, first, 0.32)
    for index in range(12):
        phase = (index / 12 + state.time * 0.25) % 1.0
        y = round(horizon + phase * phase * (canvas.height - horizon))
        canvas.line(0, y, canvas.width - 1, y, renderer.mix(second, accent, phase), 0.38)
    canvas.line(0, horizon, canvas.width - 1, horizon, WHITE, 0.75)
    draw_speed_lines(canvas, state, accent, first, 32, horizon)


def draw_launch_control(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, accent)
    draw_gauge(canvas, canvas.width * 0.2, canvas.height * 0.47, 10, math.sin(state.time * 1.5) * 0.5 + 0.5, first, accent)
    draw_gauge(canvas, canvas.width * 0.5, canvas.height * 0.47, 10, math.sin(state.time * 2.1 + 1) * 0.5 + 0.5, second, accent)
    draw_gauge(canvas, canvas.width * 0.8, canvas.height * 0.47, 10, math.cos(state.time * 1.7) * 0.5 + 0.5, accent, first)
    for row in range(5):
        y = canvas.height - 12 + row * 2
        for column in range(18):
            active = (column + row * 2 + round(state.time * 7)) % 11 < 5
            canvas.put(8 + column * 3, y, accent if active else renderer.dim(first, 0.3), 0.75)


def draw_neon_highway(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    horizon = round(canvas.height * 0.48)
    road_center_x = canvas.width / 2
    vanishing_x = road_center_x
    road_length = max(1, canvas.height - 1 - horizon)
    road_half_width = canvas.width * 0.38

    sky_height = max(1, horizon)
    for row in range(sky_height):
        amount = row / max(1, sky_height - 1)
        color = renderer.mix((5, 3, 18), (65, 12, 49), amount**2)
        if renderer.USE_COLOR:
            canvas.line(0, row, canvas.width - 1, row, color)

    sun_radius = max(4, round(min(canvas.width * 0.14, horizon * 0.46)))
    sun_x = round(road_center_x)
    sun_y = horizon - sun_radius - 1
    for offset_y in range(-sun_radius, sun_radius + 1):
        if offset_y > 0 and offset_y % 3 == 1:
            continue
        sun_width = round(math.sqrt(max(0, sun_radius**2 - offset_y**2)))
        color = renderer.mix(
            GOLD,
            MAGENTA,
            (offset_y + sun_radius) / max(1, sun_radius * 2),
        )
        canvas.line(
            sun_x - sun_width,
            sun_y + offset_y,
            sun_x + sun_width,
            sun_y + offset_y,
            color,
        )
    for index, building_x in enumerate(range(-2, canvas.width + 2, 5)):
        building_width = 2 + index % 3
        if abs(building_x - sun_x) < sun_radius + 5:
            continue
        building_height = 2 + (index * 7) % max(3, horizon // 3)
        building_top = horizon - building_height
        building_color = (7, 5, 20) if renderer.USE_COLOR else BLACK
        canvas.rectangle(
            building_x,
            building_top,
            building_width,
            building_height,
            building_color,
            filled=True,
        )
        if index % 3 == 0:
            canvas.line(
                building_x + building_width // 2,
                building_top - 2,
                building_x + building_width // 2,
                building_top,
                accent,
                0.8,
            )
        canvas.put(building_x + 1, building_top + 1, CYAN, 0.8)

    canvas.line(0, horizon, canvas.width - 1, horizon, MAGENTA, 0.95)

    for side in (-1, 1):
        edge_x = road_center_x + side * road_half_width
        canvas.line(
            vanishing_x,
            horizon,
            edge_x,
            canvas.height - 1,
            CYAN,
            0.75,
        )

    left_road_x = road_center_x - road_half_width
    right_road_x = road_center_x + road_half_width
    for index in range(7):
        phase = (index / 7 + state.time * 0.55) % 1.0
        depth = phase**2
        y = round(horizon + depth * road_length)
        left_edge = round(vanishing_x + (left_road_x - vanishing_x) * depth)
        right_edge = round(vanishing_x + (right_road_x - vanishing_x) * depth)
        color = renderer.dim(renderer.mix(second, accent, phase), 0.35 + depth * 0.5)
        if left_edge > 0:
            canvas.line(
                0,
                y,
                left_edge - 2,
                y,
                color,
                0.22 + depth * 0.35,
            )
        if right_edge < canvas.width - 1:
            canvas.line(
                right_edge + 2,
                y,
                canvas.width - 1,
                y,
                color,
                0.22 + depth * 0.35,
            )

    # Project equally spaced road markings: distant dashes shrink and bunch up.
    for y in range(horizon + 1, canvas.height):
        depth = (y - horizon) / road_length
        distance = 1 / depth
        if (distance + state.time * 3.5) % 2.4 >= 1.0:
            continue
        half_width = round(depth * canvas.width * 0.014)
        for x in range(round(road_center_x) - half_width,
                       round(road_center_x) + half_width + 1):
            canvas.put(x, y, renderer.mix(GOLD, WHITE, depth * 0.4))


def draw_turbine(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, second)
    cx, cy = canvas.width / 2, canvas.height * 0.48
    radius = min(canvas.width, canvas.height) * 0.32
    ring(canvas, cx, cy, radius, first, 0.9)
    ring(canvas, cx, cy, radius - 3, renderer.dim(second, 0.5), 0.75)
    blade_count = 9
    rotation = state.time * 2.8
    for index in range(blade_count):
        angle = rotation + index / blade_count * math.tau
        inner_x, inner_y = polar(cx, cy, 3, angle)
        outer_x, outer_y = polar(cx, cy, radius - 4, angle + 0.32, 0.55)
        bend_x, bend_y = polar(cx, cy, radius * 0.56, angle - 0.2, 0.55)
        canvas.line(inner_x, inner_y, bend_x, bend_y, accent, 0.8)
        canvas.line(bend_x, bend_y, outer_x, outer_y, first, 0.8)
    canvas.glow(round(cx), round(cy), WHITE, radius=4, opacity=0.6)
    canvas.put(round(cx), round(cy), WHITE)


def draw_vector_chase(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, accent)
    cx, cy = canvas.width / 2, canvas.height / 2
    for index in range(20):
        phase = (index / 20 + state.time * 0.34) % 1.0
        radius = 3 + phase * min(canvas.width, canvas.height) * 0.6
        angle = index * 1.73 + state.time * (0.2 if index % 2 else -0.2)
        x, y = polar(cx, cy, radius, angle, 0.56)
        tail_x, tail_y = polar(cx, cy, radius - 8 * (1 - phase), angle + math.pi, 0.56)
        color = renderer.mix(first, second, phase)
        canvas.line(tail_x, tail_y, x, y, color, 0.25 + phase * 0.6)
        canvas.glow(x, y, accent, radius=1, opacity=0.4)
    canvas.put(round(cx), round(cy), WHITE)


def draw_reentry(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, first)
    cx = canvas.width / 2
    shield_y = canvas.height * 0.48 + math.sin(state.time * 0.9) * 2
    shield_width = canvas.width * 0.3
    canvas.line(cx - shield_width, shield_y, cx, shield_y + 8, WHITE, 0.9)
    canvas.line(cx + shield_width, shield_y, cx, shield_y + 8, WHITE, 0.9)
    canvas.line(cx - shield_width, shield_y, cx + shield_width, shield_y, first, 0.9)
    for index in range(28):
        angle = math.pi + (index / 28 - 0.5) * 1.8
        length = 8 + (index % 7) * 2 + math.sin(state.time * 7 + index) * 2
        start_x, start_y = polar(cx, shield_y, shield_width * 0.8, angle, 0.55)
        end_x, end_y = polar(start_x, start_y, length, angle, 0.55)
        canvas.line(start_x, start_y, end_x, end_y, renderer.mix(accent, GOLD, index / 28), 0.4)
    draw_speed_lines(canvas, state, second, accent, 28, shield_y)


def draw_drone_swarm(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    draw_frame(canvas, second)
    cx, cy = canvas.width / 2, canvas.height * 0.47
    ring(canvas, cx, cy, 7, accent, 0.7, phase=state.time)
    for index in range(14):
        orbit = 10 + (index % 4) * 4
        angle = state.time * (0.4 + index % 3 * 0.12) + index * 2.4
        x, y = polar(cx, cy, orbit, angle, 0.56)
        color = renderer.mix(first, second, index / 14)
        canvas.glow(x, y, color, radius=2, opacity=0.48)
        canvas.put(x, y, WHITE if index % 4 == 0 else color, 0.95)
        if index % 2 == 0:
            canvas.line(cx, cy, x, y, color, 0.11)
    draw_particles(canvas, state, first, accent, 0.8)


def draw_braille_starfield(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, _ = state.palette()
    cx, cy = canvas.width / 2, canvas.height / 2
    for index in range(100):
        angle = index * 2.39996
        depth = (index * 0.618 + state.time * 0.38) % 1
        radius = 2 + depth**2 * math.hypot(cx, cy)
        tail = max(1, radius - depth * 12)
        x, y = polar(cx, cy, radius, angle)
        tx, ty = polar(cx, cy, tail, angle)
        canvas.line(tx, ty, x, y, renderer.mix(first, second, depth))


def draw_braille_wave(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, _ = state.palette()
    for row in range(12):
        depth = row / 11
        previous = None
        for x in range(canvas.width):
            wave = math.sin(x / canvas.width * 10 - state.time * 2 + depth * 4)
            wave += 0.35 * math.sin(x / canvas.width * 23 + state.time)
            y = canvas.height * (0.18 + depth * 0.63 + wave * 0.09)
            if previous is not None:
                canvas.line(x - 1, previous, x, y, renderer.mix(first, second, depth))
            previous = y


def draw_braille_tunnel(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, _ = state.palette()
    cx, cy = canvas.width / 2, canvas.height / 2
    for index in range(12):
        depth = (index / 12 + state.time * 0.23) % 1
        radius = 2 + depth**2 * max(canvas.width, canvas.height) * 0.65
        rotation = state.time * 0.3 + depth * 0.9
        points = [polar(cx, cy, radius, rotation + i * math.tau / 6) for i in range(6)]
        for i, (x, y) in enumerate(points):
            nx, ny = points[(i + 1) % 6]
            canvas.line(x, y, nx, ny, renderer.mix(first, second, depth))


def draw_braille_helix(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, accent = state.palette()
    cy = canvas.height / 2
    radius = canvas.height * 0.3
    previous = None
    for x in range(canvas.width):
        phase = x / canvas.width * math.tau * 2 - state.time * 2
        y1, y2 = cy + math.sin(phase) * radius, cy - math.sin(phase) * radius
        if x % 8 == 0:
            canvas.line(x, y1, x, y2, renderer.dim(accent, 0.5))
        if previous is not None:
            canvas.line(x - 1, previous[0], x, y1, first)
            canvas.line(x - 1, previous[1], x, y2, second)
        previous = y1, y2


def draw_braille_vortex(canvas: renderer.PixelCanvas, state: GalleryState) -> None:
    first, second, _ = state.palette()
    cx, cy = canvas.width / 2, canvas.height / 2
    for arm in range(5):
        previous = None
        for step in range(160):
            depth = step / 159
            angle = arm * math.tau / 5 + depth * 7 - state.time * 1.5
            radius = 2 + depth * min(cx, cy) * 0.92
            x, y = polar(cx, cy, radius, angle)
            if previous is not None:
                canvas.line(*previous, x, y, renderer.mix(first, second, depth))
            previous = x, y


EXAMPLES: tuple[Example, ...] = (
    Example("VELOCITY CORE", "analogue speedometer", "gauge / boost / telemetry", draw_velocity_core),
    Example("BRAILLE OVERDRIVE", "high-speed instrument panel", "braille / gauges / boost", draw_braille_overdrive, braille=True),
    Example("AFTERBURNER", "jet engine thrust", "flame / exhaust / heat", draw_afterburner),
    Example("WARP TUNNEL", "high-speed transit", "tunnel / pulse / streaks", draw_warp_tunnel),
    Example("ROCKET LAUNCH", "vertical ascent", "rocket / smoke / stars", draw_rocket_launch),
    Example("ORBITAL RADAR", "sweep and contacts", "radar / targets / scan", draw_orbital_radar),
    Example("HYPERDRIVE GRID", "perspective acceleration", "grid / horizon / vector", draw_hyperdrive_grid),
    Example("LAUNCH CONTROL", "multi-instrument panel", "dashboard / gauges / bars", draw_launch_control),
    Example("NEON HIGHWAY", "retro-futurist road", "road / 2 lanes / center line", draw_neon_highway),
    Example("TURBINE", "rotating propulsion", "rotor / blades / energy", draw_turbine),
    Example("VECTOR CHASE", "particles at velocity", "vectors / trails / core", draw_vector_chase),
    Example("RE-ENTRY", "atmospheric descent", "shield / plasma / heat", draw_reentry),
    Example("DRONE SWARM", "orbital formation", "drones / orbit / network", draw_drone_swarm),
    Example("BRAILLE STARFIELD", "stellar acceleration", "braille / stars / trails", draw_braille_starfield, braille=True),
    Example("BRAILLE WAVE", "flowing wave surface", "braille / waves / flow", draw_braille_wave, braille=True),
    Example("BRAILLE TUNNEL", "rotating hexagonal transit", "braille / tunnel / speed", draw_braille_tunnel, braille=True),
    Example("BRAILLE HELIX", "rotating double helix", "braille / helix / rotation", draw_braille_helix, braille=True),
    Example("BRAILLE VORTEX", "spiral energy field", "braille / spiral / vortex", draw_braille_vortex, braille=True),
)


def render_catalog(width: int, height: int, state: GalleryState, page: int) -> str:
    page_size = 10
    page_count = math.ceil(len(EXAMPLES) / page_size)
    page = max(0, min(page, page_count - 1))
    first, second, accent = state.palette()
    lines = [
        ERASE_LINE + renderer.styled("  KEYGRAPHY // SPEED PIXEL GALLERY", first, bold=True),
        ERASE_LINE + renderer.styled(
            f"  CATALOG PAGE {page + 1}/{page_count}  |  {len(EXAMPLES):02d} VISUAL DIRECTIONS",
            second,
        ),
        ERASE_LINE + "",
    ]
    start = page * page_size
    entries = EXAMPLES[start : start + page_size]
    rows = math.ceil(len(entries) / 2)
    column_width = max(28, width // 2 - 2)
    for row in range(rows):
        chunks: list[str] = []
        for column in range(2):
            index = row + column * rows
            if index >= len(entries):
                continue
            number = start + index + 1
            example = entries[index]
            marker = ">" if number - 1 == state.example else " "
            value = f"{marker}{number:02d}  {example.title}"
            color = accent if number - 1 == state.example else first
            chunks.append(renderer.styled(value[:column_width].ljust(column_width), color, bold=number - 1 == state.example))
        lines.append(ERASE_LINE + "  " + "  ".join(chunks))
    while len(lines) < height - 2:
        lines.append(ERASE_LINE)
    lines.append(ERASE_LINE + renderer.styled("  1-9/0 select   n/p page   g close   m palette   q exit", accent))
    lines.append(ERASE_LINE + renderer.styled("  Choose a visual direction to carry into the Keygraphy interface.", second))
    return HOME + "\r\n".join(lines[:height]) + RESET + "\x1b[J"


def render_gallery(width: int, height: int, state: GalleryState, catalog: bool, page: int, fps: float) -> str:
    if catalog:
        return render_catalog(width, height, state, page)
    if width < 60 or height < 18:
        message = "KEYGRAPHY SPEED GALLERY needs a terminal of at least 60x18"
        return HOME + ERASE_LINE + renderer.styled(message[:width], GOLD, bold=True) + "\r\n" + "\x1b[J"

    example = EXAMPLES[state.example]
    first, second, accent = state.palette()
    main_rows = height - 6
    canvas = renderer.PixelCanvas(width * 2, main_rows * 4) if example.braille else renderer.PixelCanvas(width, main_rows * 2)
    example.draw(canvas, state)
    if example.braille:
        dots = renderer.BrailleCanvas(width, main_rows)
        for y in range(canvas.height):
            for x in range(canvas.width):
                color = canvas.pixels[y * canvas.width + x]
                if color is not None:
                    dots.dot(x, y, color)
        scene_lines = dots.render()
    else:
        scene_lines = renderer.render_halfblocks(canvas)
    header = renderer.fit_text(
        f"  KEYGRAPHY // SPEED PIXEL GALLERY     {state.example + 1:02d}/{len(EXAMPLES):02d}",
        width,
    )
    title = renderer.fit_text(f"  {example.title}  |  {example.subtitle}  |  {example.tags}", width)
    footer = renderer.fit_text("  n/p next/prev   g catalog   m palette   space pause   r reseed   q/esc exit", width)
    page_hint = renderer.fit_text("  Numbered visual direction for the future Keygraphy frontend", width)
    lines = [
        ERASE_LINE + renderer.styled(header, first, bold=True),
        ERASE_LINE + renderer.styled(title, second),
        *renderer.draw_braille_strip(width, state),
        *scene_lines,
        ERASE_LINE + renderer.styled(footer, accent),
        ERASE_LINE + renderer.styled(page_hint, first),
    ]
    return HOME + "\r\n".join(lines) + RESET + "\x1b[J"


def snapshot(plain: bool = False, example_number: int = 1) -> None:
    renderer.configure_output(plain)
    width, height = shutil.get_terminal_size((80, 24))
    state = GalleryState(seed=7)
    state.example = max(0, min(len(EXAMPLES) - 1, example_number - 1))
    state.update(1 / 30, width, max(1, (height - 6) * 2))
    frame = render_gallery(width, height, state, False, 0, 30.0)
    if plain:
        frame = renderer.without_ansi(frame)
    sys.stdout.write(frame.rstrip("\n") + "\n")


def choose_digit(key: str, page: int) -> int | None:
    if key == "0":
        offset = 9
    elif "1" <= key <= "9":
        offset = int(key) - 1
    else:
        return None
    selected = page * 10 + offset
    return selected if selected < len(EXAMPLES) else None


def run(fps: int, max_frames: int = 0) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty() or not renderer.terminal_supports_controls():
        snapshot(plain=True)
        return
    renderer.configure_output()
    fps = max(10, min(60, fps))
    frame_duration = 1 / fps
    state = GalleryState()
    catalog = False
    page = 0
    frame_count = 0
    measured_fps = float(fps)
    last_time = time.monotonic()
    vt_state = renderer.enable_windows_vt()
    sys.stdout.write(HIDE_CURSOR + renderer.CLEAR)
    sys.stdout.flush()
    try:
        with renderer.raw_terminal():
            while True:
                frame_started = time.monotonic()
                delta = min(0.1, frame_started - last_time)
                last_time = frame_started
                width, height = shutil.get_terminal_size((80, 24))
                main_height = max(1, (height - 6) * 2)
                if delta > 0.005:
                    measured_fps = measured_fps * 0.9 + (1 / delta) * 0.1
                if not state.paused and not catalog:
                    state.update(delta, width, main_height)
                key = renderer.read_key()
                if key is not None:
                    lowered = key.lower()
                    if key in ("\x03", "\x1b") or lowered == "q":
                        break
                    if key == " ":
                        state.paused = not state.paused
                    elif lowered == "g":
                        catalog = not catalog
                        page = state.example // 10
                    elif lowered == "m":
                        state.cycle_mode()
                    elif lowered == "r":
                        state.reseed(width, main_height)
                    elif catalog and lowered in {"n", "p"}:
                        page_count = math.ceil(len(EXAMPLES) / 10)
                        page = (page + (1 if lowered == "n" else -1)) % page_count
                    elif catalog:
                        selected = choose_digit(key, page)
                        if selected is not None:
                            state.example = selected
                            catalog = False
                    elif lowered in {"n", "]", "l"}:
                        state.example = (state.example + 1) % len(EXAMPLES)
                    elif lowered in {"p", "[", "h"}:
                        state.example = (state.example - 1) % len(EXAMPLES)
                    else:
                        selected = choose_digit(key, 0)
                        if selected is not None:
                            state.example = selected

                sys.stdout.write(render_gallery(width, height, state, catalog, page, measured_fps))
                sys.stdout.flush()
                frame_count += 1
                if max_frames and frame_count >= max_frames:
                    break
                time.sleep(max(0, frame_duration - (time.monotonic() - frame_started)))
    finally:
        sys.stdout.write(RESET + SHOW_CURSOR + "\r\n")
        sys.stdout.flush()
        renderer.restore_windows_vt(vt_state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fps", type=int, default=30, help="límite de cuadros por segundo")
    parser.add_argument("--frames", type=int, default=0, help="termina después de N cuadros")
    parser.add_argument("--snapshot", action="store_true", help="renderiza un ejemplo estático")
    parser.add_argument("--plain", action="store_true", help="quita colores y secuencias ANSI")
    parser.add_argument("--example", type=int, default=1, help="número del ejemplo para --snapshot")
    args = parser.parse_args()
    if args.snapshot:
        snapshot(args.plain, args.example)
        return 0
    if args.plain:
        parser.error("--plain solo se puede usar junto con --snapshot")
    run(args.fps, args.frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
