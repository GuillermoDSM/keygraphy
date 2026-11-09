#!/usr/bin/env python3
"""A minimal adaptive typing tutor for the terminal."""

from __future__ import annotations

import argparse
from bisect import bisect_right
import curses
import json
import locale
import math
import os
import random
import re
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable


APP_NAME = "keygraphy"
VERSION = "0.5.0"
LETTER_ORDER = ""
KEY_ORDER = ""
CAPITAL_ORDER = ""
LETTER_ORDERS = {
    "es-la": "eaosnirldctumpgbvóqfhíájzéyxñúkwü",
    "en-us": "eiasnrtolcdpumghbyfvwkxjqz",
}
LEGACY_LETTER_ORDER = "eaosrnidlctumpbgvyqhfzjxkwñ"
PUNCTUATION_ORDERS = {
    "es-la": ".,",
    "en-us": ".,'",
}
CONTRACTIONS = (
    "I'm", "I've", "I'll", "I'd",
    "you're", "you've", "you'll", "you'd",
    "he's", "she's", "it's", "we're", "we've", "we'll", "we'd",
    "they're", "they've", "they'll", "they'd",
    "that's", "there's", "what's", "let's", "who's", "here's",
    "don't", "can't", "won't", "isn't", "aren't", "wasn't", "weren't",
    "didn't", "doesn't", "couldn't", "shouldn't", "wouldn't",
    "hasn't", "haven't",
)
INITIAL_LETTERS = 6
TARGET_WPM = 35
MIN_TARGET_WPM = 15
MAX_TARGET_WPM = 150
TARGET_WPM_STEP = 5
DEFAULT_ESC_DELAY_MS = 50
LESSON_LENGTH = 120
RESULT_FRAME_MS = 16
RESULT_COUNT_MS_PER_UNIT = 2
RESULT_WPM_MS_PER_UNIT = 20
PARTIAL_BLOCKS = "▏▎▍▌▋▊▉"
SPEED_FILTER_ALPHA = 0.1
# Physical key presses for the initial Spanish dead-key keyboard assumption.
# These costs are independent from the selected word package.
DEFAULT_KEY_COSTS = {**dict.fromkeys("áéíóú", 2), "ü": 3}
MIN_WORD_POOL = 15
MAX_FREQUENT_WORDS = 1000
FOCUSED_WORD_RATIO = 0.5
FOCUSED_MARK_RATIO = 0.35
REVIEW_MARK_RATIO = 0.12
CAPITAL_STARTER_LIMIT = 40
POST_ALPHABET_FOCUS_SESSIONS = 3
DATA_DIR = Path(__file__).resolve().parent / "data"
BOOK_DIR = DATA_DIR / "books"
WORD_PACKAGES = {
    "es-la": DATA_DIR / "words-es-la.json",
    "en-us": DATA_DIR / "words-en-us.json",
}
DEFAULT_WORD_PACKAGE = "es-la"
MODES = ("practice", "book")
KEYBOARD_VIEWS = ("letters", "keyboard")
DEFAULT_KEYBOARD_VIEW = "keyboard"
UI_LANGUAGES = ("en", "es")
DEFAULT_UI_LANGUAGE = "en"
UI_LANGUAGE_LABELS = {"en": "English", "es": "Español"}
KEYBOARD_LANGUAGES = ("es", "en")
DEFAULT_KEYBOARD_LANGUAGE = "es"
KEYBOARD_LANGUAGE_LABELS = {"es": "Español", "en": "English (US)"}
BOOK_PATHS = {
    "la-iliada": BOOK_DIR / "la-iliada.json",
    "la-odisea": BOOK_DIR / "la-odisea.json",
}
BOOK_LABELS = {"la-iliada": "La Ilíada", "la-odisea": "La Odisea"}
DEFAULT_BOOK = "la-iliada"
BOOK_LEVEL_MIN_ATTEMPTS = 500
BOOK_LEVEL_ACCURACY = 0.95
BOOK_LINE_WIDTH = 72
BOOK_LEVELS = (
    ("words", ""),
    ("accents", ""),
    ("comma", ","),
    ("period", "."),
    ("semicolon", ";"),
    ("colon", ":"),
    ("question", "¿?"),
    ("exclamation", "¡!"),
    ("dashes", "-—"),
    ("quotes", "\"'«»“”"),
    ("parentheses", "()"),
    ("complete", "*"),
)
UNTILDED_TRANSLATION = str.maketrans("áéíóúü", "aeiouu")
UI_LANGUAGE = DEFAULT_UI_LANGUAGE
TRANSLATIONS = {
    "en": {
        "options.title": "Options",
        "options.language": "Language",
        "options.keyboard": "Keyboard",
        "options.mode": "Mode",
        "options.source": "Source",
        "options.target": "Target",
        "options.keyboard_view": "Keyboard view",
        "mode.practice": "Adaptive practice",
        "mode.book": "Book transcription",
        "view.letters": "Letter bar",
        "view.keyboard": "Keyboard",
        "package.es-la": "Spanish · Latin America",
        "package.en-us": "English · United States",
        "unit.wpm": "wpm",
        "terminal.too_small": "Terminal too small (minimum 42x10)",
        "shift": "⇧ Shift",
        "restart.exercise": "Exercise restarted",
        "restart.fragment": "Fragment restarted",
        "practice.all_mastered": "All keys mastered",
        "practice.feedback": (
            "current {current} ms · best {best} ms · target {target} ms/keystroke"
        ),
        "book.level": "Level: {label}",
        "book.level_progress": (
            "Level: {label} · {attempts}/{minimum} keystrokes · "
            "{accuracy:.0%}/{target:.0%}"
        ),
        "book.fragment": "fragment {current}/{total}",
        "book.completed": "{title} completed",
        "book_level.words": "words only",
        "book_level.accents": "accents",
        "book_level.comma": "comma",
        "book_level.period": "period",
        "book_level.semicolon": "semicolon",
        "book_level.colon": "colon",
        "book_level.question": "question marks",
        "book_level.exclamation": "exclamation marks",
        "book_level.dashes": "dashes",
        "book_level.quotes": "quotes",
        "book_level.parentheses": "parentheses",
        "book_level.complete": "full text",
        "result.current": "CURRENT",
        "result.best": "BEST",
        "result.target": "TARGET",
        "result.unit_ms": "ms",
        "result.ms_keystroke": "ms/keystroke",
        "result.title.mastery": "· ALL KEYS MASTERED ·",
        "result.title.alphabet": "· ALPHABET COMPLETE ·",
        "result.title.capitals": "· CAPITALS UNLOCKED ·",
        "result.title.marks": "· MARKS UNLOCKED ·",
        "result.title.new_capital": "· NEW CAPITAL ·",
        "result.title.new_mark": "· NEW MARK ·",
        "result.title.new_letter": "· NEW LETTER ·",
        "result.title.new_record": "· NEW RECORD ·",
    },
    "es": {
        "options.title": "Opciones",
        "options.language": "Idioma",
        "options.keyboard": "Teclado",
        "options.mode": "Modo",
        "options.source": "Fuente",
        "options.target": "Objetivo",
        "options.keyboard_view": "Ver teclado",
        "mode.practice": "Práctica adaptativa",
        "mode.book": "Transcribir libro",
        "view.letters": "Barra de letras",
        "view.keyboard": "Teclado",
        "package.es-la": "Español · Latinoamérica",
        "package.en-us": "English · United States",
        "unit.wpm": "ppm",
        "terminal.too_small": "Terminal demasiado pequeña (mínimo 42x10)",
        "shift": "⇧ Mayús",
        "restart.exercise": "Ejercicio reiniciado",
        "restart.fragment": "Fragmento reiniciado",
        "practice.all_mastered": "Todas las teclas dominadas",
        "practice.feedback": (
            "actual {current} ms · mejor {best} ms · objetivo {target} ms/pulsación"
        ),
        "book.level": "Nivel: {label}",
        "book.level_progress": (
            "Nivel: {label} · {attempts}/{minimum} pulsaciones · "
            "{accuracy:.0%}/{target:.0%}"
        ),
        "book.fragment": "fragmento {current}/{total}",
        "book.completed": "{title} completada",
        "book_level.words": "solo palabras",
        "book_level.accents": "tildes",
        "book_level.comma": "coma",
        "book_level.period": "punto",
        "book_level.semicolon": "punto y coma",
        "book_level.colon": "dos puntos",
        "book_level.question": "interrogación",
        "book_level.exclamation": "exclamación",
        "book_level.dashes": "guiones",
        "book_level.quotes": "comillas",
        "book_level.parentheses": "paréntesis",
        "book_level.complete": "texto completo",
        "result.current": "ACTUAL",
        "result.best": "MEJOR",
        "result.target": "OBJETIVO",
        "result.unit_ms": "ms",
        "result.ms_keystroke": "ms/pulsación",
        "result.title.mastery": "· DOMINIO COMPLETO ·",
        "result.title.alphabet": "· ALFABETO COMPLETO ·",
        "result.title.capitals": "· MAYÚSCULAS DESBLOQUEADAS ·",
        "result.title.marks": "· SIGNOS DESBLOQUEADOS ·",
        "result.title.new_capital": "· MAYÚSCULA NUEVA ·",
        "result.title.new_mark": "· SIGNO NUEVO ·",
        "result.title.new_letter": "· LETRA NUEVA ·",
        "result.title.new_record": "· NUEVO RÉCORD ·",
    },
}


def set_ui_language(language: str) -> None:
    global UI_LANGUAGE
    UI_LANGUAGE = language if language in UI_LANGUAGES else DEFAULT_UI_LANGUAGE


def translate(key: str, **values: object) -> str:
    language = TRANSLATIONS.get(UI_LANGUAGE, TRANSLATIONS[DEFAULT_UI_LANGUAGE])
    template = language.get(key) or TRANSLATIONS[DEFAULT_UI_LANGUAGE].get(key, key)
    return template.format(**values) if values else template
ERROR_COLOR = 196
ERROR_RGB = (235, 71, 71)
CURRENT_BACKGROUND = 240
BAR_COLOR_BASE = 200
BAR_COLOR_COUNT = 4
BAR_RGBS = (
    (82, 84, 90),
    (110, 112, 119),
    (140, 142, 150),
    (172, 176, 186),
)
KEYBOARD_ROWS = {
    "es": (
        ("q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "´", "¨"),
        ("a", "s", "d", "f", "g", "h", "j", "k", "l", "ñ"),
        ("z", "x", "c", "v", "b", "n", "m", ",", ".", "-", "'"),
    ),
    "en": (
        ("q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "[", "]"),
        ("a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'"),
        ("z", "x", "c", "v", "b", "n", "m", ",", ".", "/", "-"),
    ),
}
KEYBOARD_FINGER_GROUPS = {
    "es": (
        ("q", "a", "z", "p", "ñ", "-", "´", "¨", "'"),
        ("w", "s", "x", "o", "l", "."),
        ("e", "d", "c", "i", "k", ","),
        ("r", "f", "v", "t", "g", "b", "y", "h", "n", "u", "j", "m"),
    ),
    "en": (
        ("q", "a", "z", "p", ";", "/", "[", "]", "'", "-"),
        ("w", "s", "x", "o", "l", "."),
        ("e", "d", "c", "i", "k", ","),
        ("r", "f", "v", "t", "g", "b", "y", "h", "n", "u", "j", "m"),
    ),
}
KEYBOARD_FINGER_BY_KEY = {
    language: {
        key: finger
        for finger, group in enumerate(groups)
        for key in group
    }
    for language, groups in KEYBOARD_FINGER_GROUPS.items()
}
KEYBOARD_FINGER_COUNT = len(KEYBOARD_FINGER_GROUPS[DEFAULT_KEYBOARD_LANGUAGE])
KEYBOARD_HAND_GAP = 2
KEYBOARD_COLOR_BASE = 204
KEYBOARD_RGBS = (
    (62, 32, 47),
    (27, 43, 68),
    (27, 56, 42),
    (68, 48, 23),
)
KEYBOARD_256_BACKGROUNDS = (52, 18, 22, 58)


def load_word_list(path: Path) -> tuple[str, ...]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No se pudo cargar el corpus de palabras: {path}") from error
    if not isinstance(raw, list) or not 5_000 <= len(raw) <= 10_000:
        raise RuntimeError("El corpus debe contener entre 5.000 y 10.000 palabras")
    words: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            word = entry
        elif isinstance(entry, dict):
            word = entry.get("word")
        else:
            word = None
        if not isinstance(word, str) or not word:
            raise RuntimeError("El corpus contiene entradas inválidas")
        words.append(word)
    return tuple(words)


def load_letter_order(path: Path, fallback: str) -> str:
    metadata_path = path.with_name(f"{path.stem}.meta.json")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        letter_order = metadata.get("letter_order")
    except (OSError, json.JSONDecodeError):
        return fallback
    if not isinstance(letter_order, str) or not letter_order:
        return fallback
    return letter_order


WORDS: tuple[str, ...] = ()


def select_word_package(name: str) -> None:
    global CAPITAL_ORDER, KEY_ORDER, LETTER_ORDER, WORDS
    WORDS = load_word_list(WORD_PACKAGES[name])
    LETTER_ORDER = load_letter_order(WORD_PACKAGES[name], LETTER_ORDERS[name])
    LETTER_ORDERS[name] = LETTER_ORDER
    CAPITAL_ORDER = "".join(
        letter.upper()
        for letter in LETTER_ORDER
        if any(word.startswith(letter) for word in WORDS)
    )
    KEY_ORDER = LETTER_ORDER + CAPITAL_ORDER + PUNCTUATION_ORDERS[name]


select_word_package(DEFAULT_WORD_PACKAGE)


@dataclass
class LetterStat:
    """Smoothed milliseconds per press, plus total character production time."""

    hits: int = 0
    misses: int = 0
    time_ms: float | None = None
    best_time_ms: float | None = None
    raw_time_ms: float | None = None
    best_raw_time_ms: float | None = None

    @property
    def attempts(self) -> int:
        return self.hits + self.misses

    @property
    def accuracy(self) -> float:
        return self.hits / self.attempts if self.attempts else 0.0

    def append_lesson(
        self,
        hits: int,
        misses: int,
        average_time_ms: float | None,
        key_cost: int = 1,
    ) -> None:
        self.hits += hits
        self.misses += misses
        if average_time_ms is None:
            return
        if self.raw_time_ms is None and self.time_ms is not None:
            self.raw_time_ms = self.time_ms * key_cost
        if self.best_raw_time_ms is None and self.best_time_ms is not None:
            self.best_raw_time_ms = self.best_time_ms * key_cost
        if self.raw_time_ms is None:
            self.raw_time_ms = average_time_ms
        else:
            self.raw_time_ms = (
                self.raw_time_ms * (1 - SPEED_FILTER_ALPHA)
                + average_time_ms * SPEED_FILTER_ALPHA
            )
        self.best_raw_time_ms = min(
            self.best_raw_time_ms or float("inf"), self.raw_time_ms
        )
        self.time_ms = self.raw_time_ms / key_cost
        self.best_time_ms = self.best_raw_time_ms / key_cost


@dataclass
class BookPosition:
    section: int = 0
    chunk: int = 0
    completed: bool = False
    revision: str = ""
    offset: int = 0


@dataclass
class Progress:
    target_wpm: int = TARGET_WPM
    keyboard_view: str = DEFAULT_KEYBOARD_VIEW
    ui_language: str = DEFAULT_UI_LANGUAGE
    keyboard_language: str = DEFAULT_KEYBOARD_LANGUAGE
    letters: dict[str, LetterStat] = field(default_factory=dict)
    best_wpm_by_package: dict[str, float] = field(default_factory=dict)
    post_alphabet_focus: str | None = None
    post_alphabet_focus_sessions: int = 0
    word_package: str = DEFAULT_WORD_PACKAGE
    mode: str = "practice"
    selected_book: str = DEFAULT_BOOK
    book_level: int = 0
    book_level_attempts: int = 0
    book_level_correct: int = 0
    books: dict[str, BookPosition] = field(default_factory=dict)
    key_costs: dict[str, int] = field(default_factory=dict)

    def key_cost(self, character: str) -> int:
        if character in self.key_costs:
            return self.key_costs[character]
        base = character.lower()
        return self.key_costs.get(base, DEFAULT_KEY_COSTS.get(base, 1)) + int(
            character.isupper()
        )

    def set_key_cost(self, character: str, cost: int) -> None:
        if len(character) != 1 or not character.isprintable():
            raise ValueError("El coste requiere un carácter imprimible")
        if type(cost) is not int or not 1 <= cost <= 10:
            raise ValueError("El coste debe ser un entero entre 1 y 10")
        previous = {letter: self.key_cost(letter) for letter in self.letters}
        self.key_costs[character] = cost
        for letter, stat in self.letters.items():
            if stat.raw_time_ms is None and stat.time_ms is not None:
                stat.raw_time_ms = stat.time_ms * previous[letter]
            if stat.best_raw_time_ms is None and stat.best_time_ms is not None:
                stat.best_raw_time_ms = stat.best_time_ms * previous[letter]
            stat.time_ms = (
                stat.raw_time_ms / self.key_cost(letter)
                if stat.raw_time_ms is not None else None
            )
            stat.best_time_ms = (
                stat.best_raw_time_ms / self.key_cost(letter)
                if stat.best_raw_time_ms is not None else None
            )
        self.reset_post_alphabet_focus()

    @property
    def active_keys(self) -> str:
        included: list[str] = []
        for key in KEY_ORDER:
            if len(included) < INITIAL_LETTERS:
                included.append(key)
            elif self.best_confidence(key) >= 1:
                included.append(key)
            elif all(self.best_confidence(current) >= 1 for current in included):
                included.append(key)
        return "".join(included)

    @property
    def keys_complete(self) -> bool:
        return all(self.best_confidence(key) >= 1 for key in KEY_ORDER)

    @property
    def target_time_ms(self) -> float:
        return 60_000 / (self.target_wpm * 5)

    def stat(self, letter: str) -> LetterStat:
        return self.letters.setdefault(letter, LetterStat())

    def confidence(self, letter: str) -> float:
        stat = self.letters.get(letter)
        if stat is None:
            return 0.0
        return self.target_time_ms / stat.time_ms if stat.time_ms else 0.0

    def best_confidence(self, letter: str) -> float:
        stat = self.letters.get(letter)
        best_time_ms = stat.best_time_ms if stat is not None else None
        return self.target_time_ms / best_time_ms if best_time_ms else 0.0

    def weakest_key(self) -> str | None:
        learning = [
            key
            for key in self.active_keys
            if self.best_confidence(key) < 1
        ]
        if learning:
            return min(learning, key=self.best_confidence)
        if not self.keys_complete:
            return None
        measured = [
            key
            for key in self.active_keys
            if self.letters.get(key) is not None
            and self.letters[key].time_ms is not None
        ]
        return (
            max(measured, key=lambda key: self.letters[key].time_ms)
            if measured
            else None
        )

    @property
    def best_wpm(self) -> float:
        return self.best_wpm_by_package.get(self.word_package, 0.0)

    def record_wpm(self, wpm: float) -> None:
        if wpm > self.best_wpm:
            self.best_wpm_by_package[self.word_package] = wpm

    def lesson_focus(self) -> str | None:
        if not self.keys_complete:
            return self.weakest_key()
        stored = self.post_alphabet_focus
        stored_stat = self.letters.get(stored) if stored is not None else None
        if (
            stored is not None
            and stored in self.active_keys
            and stored_stat is not None
            and stored_stat.time_ms is not None
            and self.post_alphabet_focus_sessions < POST_ALPHABET_FOCUS_SESSIONS
        ):
            return stored
        focus = self.weakest_key()
        self.post_alphabet_focus = focus
        self.post_alphabet_focus_sessions = 0
        return focus

    def record_lesson_focus(self, focus: str | None) -> None:
        if (
            self.keys_complete
            and focus is not None
            and focus == self.post_alphabet_focus
        ):
            self.post_alphabet_focus_sessions = min(
                POST_ALPHABET_FOCUS_SESSIONS,
                self.post_alphabet_focus_sessions + 1,
            )

    def reset_post_alphabet_focus(self) -> None:
        self.post_alphabet_focus = None
        self.post_alphabet_focus_sessions = 0

    def book_position(self, book: str | None = None) -> BookPosition:
        return self.books.setdefault(book or self.selected_book, BookPosition())


@dataclass(frozen=True)
class BookSection:
    title: str
    chunks: tuple[str, ...]


@dataclass(frozen=True)
class Book:
    slug: str
    title: str
    sections: tuple[BookSection, ...]
    revision: str = ""


BOOK_CACHE: dict[str, Book] = {}


def load_book(slug: str) -> Book:
    if slug in BOOK_CACHE:
        return BOOK_CACHE[slug]
    if slug not in BOOK_PATHS:
        raise RuntimeError(f"Libro desconocido: {slug}")
    path = BOOK_PATHS[slug]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        title = raw["metadata"]["title"]
        revision = raw["metadata"]["content_revision"]
        sections = tuple(
            BookSection(section["title"], tuple(section["chunks"]))
            for section in raw["sections"]
        )
        if (
            not title
            or not revision
            or not sections
            or any(not section.chunks for section in sections)
        ):
            raise ValueError
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No se pudo cargar el libro: {path}") from error
    book = Book(slug, title, sections, revision)
    BOOK_CACHE[slug] = book
    return book


def data_path() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / APP_NAME / "stats.json"


def load_progress(path: Path | None = None) -> Progress:
    path = path or data_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        word_package = raw.get("word_package", DEFAULT_WORD_PACKAGE)
        if word_package not in WORD_PACKAGES:
            word_package = DEFAULT_WORD_PACKAGE
        letter_order = LETTER_ORDERS[word_package]
        raw_letters = raw.get("letters", {})
        if not isinstance(raw_letters, dict):
            raw_letters = {}
        cost_progress = Progress()
        raw_costs = raw.get("key_costs", {})
        if isinstance(raw_costs, dict):
            for character, cost in raw_costs.items():
                try:
                    cost_progress.set_key_cost(character, cost)
                except (TypeError, ValueError):
                    continue
        normalized_timing = raw.get("timing_version") == 1
        target_wpm = max(
            MIN_TARGET_WPM,
            min(int(raw.get("target_wpm", TARGET_WPM)), MAX_TARGET_WPM),
        )
        target_time_ms = 60_000 / (target_wpm * 5)
        raw_best_wpm = raw.get("best_wpm", {})
        best_wpm_by_package: dict[str, float] = {}
        if isinstance(raw_best_wpm, dict):
            for package, value in raw_best_wpm.items():
                if package not in WORD_PACKAGES:
                    continue
                try:
                    best_wpm = float(value)
                except (TypeError, ValueError):
                    continue
                if best_wpm > 0 and math.isfinite(best_wpm):
                    best_wpm_by_package[package] = best_wpm
        elif word_package in WORD_PACKAGES:
            try:
                best_wpm = float(raw_best_wpm)
            except (TypeError, ValueError):
                best_wpm = 0.0
            if best_wpm > 0 and math.isfinite(best_wpm):
                best_wpm_by_package[word_package] = best_wpm
        raw_focus = raw.get("post_alphabet_focus")
        post_alphabet_focus = (
            raw_focus
            if isinstance(raw_focus, str)
            and raw_focus in letter_order + letter_order.upper() + ",.'"
            else None
        )
        try:
            post_alphabet_focus_sessions = max(
                0,
                min(
                    int(raw.get("post_alphabet_focus_sessions", 0)),
                    POST_ALPHABET_FOCUS_SESSIONS,
                ),
            )
        except (TypeError, ValueError):
            post_alphabet_focus_sessions = 0
        raw_keyboard_view = raw.get("keyboard_view")
        if raw_keyboard_view in KEYBOARD_VIEWS:
            keyboard_view = raw_keyboard_view
        elif "keyboard_view" not in raw:
            # Existing saves predate this preference and used the letters bar.
            keyboard_view = "letters"
        else:
            keyboard_view = DEFAULT_KEYBOARD_VIEW
        raw_ui_language = raw.get("ui_language")
        ui_language = (
            raw_ui_language
            if raw_ui_language in UI_LANGUAGES
            else DEFAULT_UI_LANGUAGE
        )
        raw_keyboard_language = raw.get("keyboard_language")
        keyboard_language = (
            raw_keyboard_language
            if raw_keyboard_language in KEYBOARD_LANGUAGES
            else DEFAULT_KEYBOARD_LANGUAGE
        )
        legacy_unlocked = max(
            INITIAL_LETTERS,
            min(
                int(raw.get("unlocked", INITIAL_LETTERS)),
                len(LEGACY_LETTER_ORDER),
            ),
        )
        legacy_mastered = set(LEGACY_LETTER_ORDER[: legacy_unlocked - 1])
        letters: dict[str, LetterStat] = {}
        for letter, values in raw_letters.items():
            if (
                letter not in letter_order + letter_order.upper() + ",.'"
                or not isinstance(values, dict)
            ):
                continue
            try:
                hits = max(0, int(values.get("hits", 0)))
                misses = max(0, int(values.get("misses", 0)))
                raw_time_ms = values.get("time_ms")
                time_ms = float(raw_time_ms) if raw_time_ms is not None else None
                raw_best_time_ms = values.get("best_time_ms")
                best_time_ms = (
                    float(raw_best_time_ms)
                    if raw_best_time_ms is not None
                    else None
                )
                if time_ms is not None and (time_ms <= 0 or not math.isfinite(time_ms)):
                    raise ValueError
                if best_time_ms is not None and (
                    best_time_ms <= 0 or not math.isfinite(best_time_ms)
                ):
                    raise ValueError
            except (TypeError, ValueError):
                continue
            if best_time_ms is None and time_ms is not None:
                # Every key before the newest legacy key had already passed the
                # old progression gate, even though that best time was not saved.
                if letter in legacy_mastered:
                    best_time_ms = min(time_ms, target_time_ms)
                else:
                    best_time_ms = time_ms
            cost = cost_progress.key_cost(letter)
            try:
                if normalized_timing:
                    total_ms = values.get("raw_time_ms")
                    best_total_ms = values.get("best_raw_time_ms")
                    total_ms = (
                        float(total_ms) if total_ms is not None
                        else time_ms * cost if time_ms is not None else None
                    )
                    best_total_ms = (
                        float(best_total_ms) if best_total_ms is not None
                        else best_time_ms * cost if best_time_ms is not None else None
                    )
                else:
                    total_ms, best_total_ms = time_ms, best_time_ms
                if any(
                    value is not None and (value <= 0 or not math.isfinite(value))
                    for value in (total_ms, best_total_ms)
                ):
                    raise ValueError
            except (TypeError, ValueError):
                continue
            letters[letter] = LetterStat(
                hits=hits,
                misses=misses,
                time_ms=total_ms / cost if total_ms is not None else None,
                best_time_ms=best_total_ms / cost if best_total_ms is not None else None,
                raw_time_ms=total_ms,
                best_raw_time_ms=best_total_ms,
            )
        mode = raw.get("mode", "practice")
        if mode not in MODES:
            mode = "practice"
        selected_book = raw.get("selected_book", DEFAULT_BOOK)
        if selected_book not in BOOK_PATHS:
            selected_book = DEFAULT_BOOK
        try:
            book_level = max(
                0,
                min(int(raw.get("book_level", 0)), len(BOOK_LEVELS) - 1),
            )
        except (TypeError, ValueError):
            book_level = 0
        try:
            book_level_attempts = max(0, int(raw.get("book_level_attempts", 0)))
        except (TypeError, ValueError):
            book_level_attempts = 0
        try:
            book_level_correct = max(
                0,
                min(int(raw.get("book_level_correct", 0)), book_level_attempts),
            )
        except (TypeError, ValueError):
            book_level_correct = 0
        raw_books = raw.get("books", {})
        if not isinstance(raw_books, dict):
            raw_books = {}
        books: dict[str, BookPosition] = {}
        for slug, values in raw_books.items():
            if slug not in BOOK_PATHS or not isinstance(values, dict):
                continue
            try:
                revision = values.get("revision", "")
                books[slug] = BookPosition(
                    section=max(0, int(values.get("section", 0))),
                    chunk=max(0, int(values.get("chunk", 0))),
                    completed=values.get("completed", False) is True,
                    revision=revision if isinstance(revision, str) else "",
                    offset=max(0, int(values.get("offset", 0))),
                )
            except (TypeError, ValueError):
                continue
        return Progress(
            target_wpm=target_wpm,
            keyboard_view=keyboard_view,
            ui_language=ui_language,
            keyboard_language=keyboard_language,
            letters=letters,
            best_wpm_by_package=best_wpm_by_package,
            post_alphabet_focus=post_alphabet_focus,
            post_alphabet_focus_sessions=post_alphabet_focus_sessions,
            word_package=word_package,
            mode=mode,
            selected_book=selected_book,
            book_level=book_level,
            book_level_attempts=book_level_attempts,
            book_level_correct=book_level_correct,
            books=books,
            key_costs=cost_progress.key_costs,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return Progress()


def save_progress(progress: Progress, path: Path | None = None) -> None:
    path = path or data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timing_version": 1,
        "key_costs": progress.key_costs,
        "target_wpm": progress.target_wpm,
        "keyboard_view": progress.keyboard_view,
        "ui_language": progress.ui_language,
        "keyboard_language": progress.keyboard_language,
        "word_package": progress.word_package,
        "best_wpm": progress.best_wpm_by_package,
        "post_alphabet_focus": progress.post_alphabet_focus,
        "post_alphabet_focus_sessions": progress.post_alphabet_focus_sessions,
        "mode": progress.mode,
        "selected_book": progress.selected_book,
        "book_level": progress.book_level,
        "book_level_attempts": progress.book_level_attempts,
        "book_level_correct": progress.book_level_correct,
        "books": {key: asdict(value) for key, value in progress.books.items()},
        "letters": {key: asdict(value) for key, value in progress.letters.items()},
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def unlock_feedback(progress: Progress) -> str:
    set_ui_language(progress.ui_language)
    if progress.keys_complete:
        return translate("practice.all_mastered")
    focus = progress.weakest_key()
    if focus is None:
        return translate("practice.all_mastered")
    stat = progress.stat(focus)
    current = f"{stat.time_ms:.0f}" if stat.time_ms is not None else "--"
    best = f"{stat.best_time_ms:.0f}" if stat.best_time_ms is not None else "--"
    return translate(
        "practice.feedback",
        current=current,
        best=best,
        target=f"{progress.target_time_ms:.0f}",
    )


def normalize_word(word: str) -> str:
    return word.lower().strip(".,;:!?¡¿\"'()")


def eligible_words(
    active_letters: str,
    focus: str | None,
) -> tuple[list[str], list[str]]:
    allowed = set(active_letters)
    eligible = [
        word
        for raw in WORDS
        if (word := normalize_word(raw))
        and len(word) > 1
        and set(word) <= allowed
    ]
    focused = [word for word in eligible if focus is None or focus in word]
    return eligible, focused


def pseudo_word(
    active_letters: str,
    focus: str | None,
    rng: random.Random,
) -> str:
    letters = [letter for letter in active_letters if letter.islower()]
    vowels = [letter for letter in letters if letter in "aeiouáéíóúü"]
    consonants = [letter for letter in letters if letter not in "aeiouáéíóúü"]
    if not vowels or not consonants:
        pool = list(letters)
        word = "".join(rng.choice(pool) for _ in range(rng.randint(3, 6)))
    else:
        size = rng.randint(2, 3)
        word = "".join(
            rng.choice(consonants) + rng.choice(vowels) for _ in range(size)
        )
    if focus is not None and focus not in word:
        position = rng.randrange(len(word) + 1)
        word = word[:position] + focus + word[position:]
    return word


def alphabet_complete(active_letters: str) -> bool:
    return set(LETTER_ORDER) <= set(active_letters)


def capitals_complete(active_keys: str) -> bool:
    return set(CAPITAL_ORDER) <= set(active_keys)


def build_word_pool(
    active_letters: str,
    focus: str | None,
    rng: random.Random,
    minimum: int = MIN_WORD_POOL,
) -> list[str]:
    eligible, focused = eligible_words(active_letters, focus)
    if focus is not None and alphabet_complete(active_letters):
        general = [word for word in eligible if focus not in word]
        focused_limit = round(MAX_FREQUENT_WORDS * FOCUSED_WORD_RATIO)
        general_limit = MAX_FREQUENT_WORDS - focused_limit
        pool = focused[:focused_limit] + general[:general_limit]
    elif focus is None:
        pool = eligible[:MAX_FREQUENT_WORDS]
    else:
        pool = focused[:MAX_FREQUENT_WORDS]
    attempts = 0
    while len(pool) < minimum and attempts < minimum * 100:
        word_focus = focus
        if focus is not None and alphabet_complete(active_letters):
            focused_count = sum(focus in word for word in pool)
            word_focus = focus if focused_count < len(pool) * FOCUSED_WORD_RATIO else None
        word = pseudo_word(active_letters, word_focus, rng)
        if word not in pool:
            pool.append(word)
        attempts += 1
    while len(pool) < minimum:
        word_focus = focus
        if focus is not None and alphabet_complete(active_letters):
            focused_count = sum(focus in word for word in pool)
            word_focus = focus if focused_count < len(pool) * FOCUSED_WORD_RATIO else None
        pool.append(pseudo_word(active_letters, word_focus, rng))
    return pool


def generate_capital_lesson(
    active_keys: str,
    focus: str,
    rng: random.Random,
    target_length: int,
) -> str:
    focus_letter = focus.lower()
    allowed = set(active_keys) | {key.lower() for key in active_keys}
    eligible = [
        word
        for raw in WORDS
        if (word := normalize_word(raw))
        and len(word) > 1
        and set(word) <= allowed
    ]
    starters = [
        word for word in eligible if word.startswith(focus_letter)
    ][:CAPITAL_STARTER_LIMIT]
    general = [
        word for word in eligible if not word.startswith(focus_letter)
    ][:MAX_FREQUENT_WORDS]
    starter_weights = [1 / (index + 1) for index in range(len(starters))]
    result: list[str] = []
    length = 0

    while length < target_length:
        if starters and (not general or rng.random() < FOCUSED_WORD_RATIO):
            word = rng.choices(starters, weights=starter_weights, k=1)[0]
            token = word.capitalize()
        else:
            token = rng.choice(general)
        if result and result[-1].lower() == token.lower():
            continue
        result.append(token)
        length += len(token) + (1 if len(result) > 1 else 0)
    return " ".join(result)


def available_contractions(active_keys: str) -> list[str]:
    allowed = set(active_keys)
    return [word for word in CONTRACTIONS if set(word) <= allowed]


def generate_mark_lesson(
    active_keys: str,
    focus: str,
    rng: random.Random,
    target_length: int,
) -> str:
    """Words with sentence punctuation; contractions train the apostrophe."""
    words = build_word_pool(active_keys, None, rng)
    contractions = available_contractions(active_keys) if focus == "'" else []
    review_marks = [
        key for key in ",.'" if key in active_keys and key != focus
    ]
    tokens: list[str] = []
    length = 0
    capitalize_next = True

    while length < target_length:
        token = rng.choice(words)
        if contractions and rng.random() < FOCUSED_WORD_RATIO:
            token = rng.choice(contractions)
        mark = ""
        if focus in ".," and rng.random() < FOCUSED_MARK_RATIO:
            mark = focus
        elif review_marks and rng.random() < REVIEW_MARK_RATIO:
            mark = rng.choice(review_marks)
        if capitalize_next:
            token = token[:1].upper() + token[1:]
        token += mark
        capitalize_next = mark == "."
        if tokens and tokens[-1].lower().rstrip(".,'") == token.lower().rstrip(".,'"):
            continue
        tokens.append(token)
        length += len(token) + (1 if len(tokens) > 1 else 0)
    return " ".join(tokens)


def generate_lesson(
    progress: Progress,
    rng: random.Random | None = None,
    target_length: int = LESSON_LENGTH,
) -> str:
    rng = rng or random.Random()
    active = progress.active_keys
    focus = progress.lesson_focus()
    if focus is not None and focus.isupper():
        return generate_capital_lesson(active, focus, rng, target_length)
    if focus is not None and focus in ",.'":
        return generate_mark_lesson(active, focus, rng, target_length)
    pool = build_word_pool(active, focus, rng)
    result: list[str] = []
    length = 0

    while length < target_length:
        word = rng.choice(pool)
        if result and result[-1] == word:
            continue
        result.append(word)
        length += len(word) + (1 if len(result) > 1 else 0)
    return " ".join(result)


def wrap_ranges(text: str, width: int) -> Iterable[tuple[int, int]]:
    start = 0
    while start < len(text):
        end = min(start + width, len(text))
        if end < len(text):
            space = text.rfind(" ", start, end + 1)
            if space > start:
                end = space
        yield start, end
        start = end + 1 if end < len(text) and text[end] == " " else end


@dataclass
class LessonSample:
    hits: int = 0
    misses: int = 0
    total_time_ms: float = 0.0
    timed_hits: int = 0


class Session:
    def __init__(self, progress: Progress, text: str) -> None:
        self.progress = progress
        self.text = text
        self.focus = progress.lesson_focus()
        self.letter_samples: dict[str, LessonSample] = {}
        self.committed = False
        self.typed: list[str] = []
        self.correct = 0
        self.attempts = 0
        self.mistake = False
        self.error_positions: set[int] = set()
        self.started_at: float | None = None
        self.last_key_at: float | None = None
        self.finished_at: float | None = None

    @property
    def complete(self) -> bool:
        return len(self.typed) >= len(self.text)

    @property
    def accuracy(self) -> float:
        return self.correct / self.attempts if self.attempts else 1.0

    @property
    def wpm(self) -> float:
        if self.started_at is None or not self.typed:
            return 0.0
        ended_at = (
            self.finished_at
            if self.finished_at is not None
            else time.monotonic()
        )
        elapsed = max(ended_at - self.started_at, 0.001)
        return (len(self.typed) / 5) / (elapsed / 60)

    def add(self, character: str, now: float | None = None) -> None:
        if self.complete:
            return
        now = now if now is not None else time.monotonic()
        if self.started_at is None:
            self.started_at = now
        expected = self.text[len(self.typed)]
        correct = character == expected
        elapsed_ms = (
            (now - self.last_key_at) * 1000 if self.last_key_at is not None else None
        )
        self.attempts += 1
        is_trigger = not self.typed
        if (
            correct
            and not is_trigger
            # Record every character that can appear in a lesson, even when
            # it is not part of the current package progression.
            and expected in LETTER_ORDER + LETTER_ORDER.upper() + ",.'"
        ):
            sample = self.letter_samples.setdefault(expected, LessonSample())
            sample.hits += 1
            if self.mistake:
                sample.misses += 1
            if (
                not self.mistake
                and elapsed_ms is not None
                and elapsed_ms > 0
            ):
                sample.total_time_ms += elapsed_ms
                sample.timed_hits += 1
        if correct:
            self.typed.append(character)
            self.correct += 1
            self.mistake = False
            if self.complete:
                self.finished_at = now
        else:
            self.mistake = True
            self.error_positions.add(len(self.typed))
        self.last_key_at = now

    def commit(self) -> None:
        if not self.complete or self.committed:
            return
        for letter, sample in self.letter_samples.items():
            average = None
            if sample.timed_hits:
                lesson_average = math.floor(
                    sample.total_time_ms / sample.timed_hits + 0.5
                )
                if 40 <= lesson_average / self.progress.key_cost(letter) <= 12_000:
                    average = lesson_average
            self.progress.stat(letter).append_lesson(
                sample.hits,
                sample.misses,
                average,
                self.progress.key_cost(letter),
            )
        self.committed = True

    def reset(self) -> None:
        self.typed.clear()
        self.correct = 0
        self.attempts = 0
        self.mistake = False
        self.error_positions.clear()
        self.letter_samples.clear()
        self.committed = False
        self.started_at = None
        self.last_key_at = None
        self.finished_at = None


def book_expected_positions(text: str, level: int) -> tuple[tuple[int, str], ...]:
    level = max(0, min(level, len(BOOK_LEVELS) - 1))
    complete_text = level == len(BOOK_LEVELS) - 1
    punctuation = "".join(characters for _, characters in BOOK_LEVELS[1 : level + 1])
    expected: list[tuple[int, str]] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character in "\r\n":
            while index + 1 < len(text) and text[index + 1] in "\r\n":
                index += 1
            expected.append((index, "\n" if complete_text else " "))
            index += 1
            continue
        if complete_text and character.isprintable():
            expected.append((index, character))
        elif character.isalpha():
            expected_character = character.lower()
            if level == 0:
                expected_character = expected_character.translate(UNTILDED_TRANSLATION)
            expected.append((index, expected_character))
        elif character == " " or character in punctuation:
            expected.append((index, character))
        index += 1
    return tuple(expected)


class BookSession:
    def __init__(self, text: str, level: int) -> None:
        self.text = text
        self.level = level
        self.expected = book_expected_positions(text, level)
        self.cursor = 0
        self.correct = 0
        self.attempts = 0
        self.mistake = False
        self.error_positions: set[int] = set()
        self.started_at: float | None = None

    @property
    def complete(self) -> bool:
        return self.cursor >= len(self.expected)

    @property
    def source_position(self) -> int:
        return self.expected[self.cursor][0] if not self.complete else len(self.text)

    @property
    def accuracy(self) -> float:
        return self.correct / self.attempts if self.attempts else 1.0

    @property
    def wpm(self) -> float:
        if self.started_at is None or not self.cursor:
            return 0.0
        elapsed = max(time.monotonic() - self.started_at, 0.001)
        return (self.cursor / 5) / (elapsed / 60)

    def add(self, character: str, now: float | None = None) -> None:
        if self.complete:
            return
        now = now if now is not None else time.monotonic()
        if self.started_at is None:
            self.started_at = now
        source_index, expected = self.expected[self.cursor]
        self.attempts += 1
        if character == expected:
            self.cursor += 1
            self.correct += 1
            self.mistake = False
        else:
            self.mistake = True
            self.error_positions.add(source_index)

    def reset(self) -> None:
        self.cursor = 0
        self.correct = 0
        self.attempts = 0
        self.mistake = False
        self.error_positions.clear()
        self.started_at = None


def book_level_feedback(progress: Progress) -> str:
    set_ui_language(progress.ui_language)
    label = translate(f"book_level.{BOOK_LEVELS[progress.book_level][0]}")
    if progress.book_level == len(BOOK_LEVELS) - 1:
        return translate("book.level", label=label)
    accuracy = (
        progress.book_level_correct / progress.book_level_attempts
        if progress.book_level_attempts
        else 1.0
    )
    return translate(
        "book.level_progress",
        label=label,
        attempts=progress.book_level_attempts,
        minimum=BOOK_LEVEL_MIN_ATTEMPTS,
        accuracy=accuracy,
        target=BOOK_LEVEL_ACCURACY,
    )


def record_book_session(progress: Progress, session: BookSession) -> str | None:
    set_ui_language(progress.ui_language)
    progress.book_level_attempts += session.attempts
    progress.book_level_correct += session.correct
    if progress.book_level >= len(BOOK_LEVELS) - 1:
        return None
    accuracy = progress.book_level_correct / max(progress.book_level_attempts, 1)
    if (
        progress.book_level_attempts >= BOOK_LEVEL_MIN_ATTEMPTS
        and accuracy >= BOOK_LEVEL_ACCURACY
    ):
        progress.book_level += 1
        progress.book_level_attempts = 0
        progress.book_level_correct = 0
        return translate(f"book_level.{BOOK_LEVELS[progress.book_level][0]}")
    return None


def advance_book_position(
    progress: Progress,
    book: Book,
    next_offset: int | None = None,
) -> bool:
    position = progress.book_position(book.slug)
    if next_offset is not None:
        section_text = book_section_text(book.sections[position.section])
        if next_offset < len(section_text):
            position.chunk = 0
            position.offset = next_offset
            return False
        position.chunk = 0
        position.offset = 0
        position.section += 1
        if position.section >= len(book.sections):
            position.section = len(book.sections) - 1
            position.offset = len(book_section_text(book.sections[-1]))
            position.completed = True
            return True
        return False
    position.offset = 0
    position.chunk += 1
    if position.chunk >= len(book.sections[position.section].chunks):
        position.section += 1
        position.chunk = 0
    if position.section >= len(book.sections):
        position.section = len(book.sections) - 1
        position.chunk = len(book.sections[-1].chunks) - 1
        position.offset = len(book.sections[-1].chunks[-1])
        position.completed = True
        return True
    return False


def current_book_chunk(progress: Progress, book: Book) -> tuple[BookPosition, str]:
    position = progress.book_position(book.slug)
    if position.revision != book.revision:
        position.section = 0
        position.chunk = 0
        position.completed = False
        position.revision = book.revision
        position.offset = 0
    if position.section >= len(book.sections):
        position.section = len(book.sections) - 1
        position.chunk = 0
    section = book.sections[position.section]
    if position.chunk >= len(section.chunks):
        position.chunk = 0
        position.offset = 0
    return position, section.chunks[position.chunk]


@lru_cache(maxsize=64)
def book_section_text(section: BookSection) -> str:
    return " ".join(section.chunks)


def current_book_text(progress: Progress, book: Book) -> tuple[BookPosition, str]:
    position, _ = current_book_chunk(progress, book)
    section = book.sections[position.section]
    if position.chunk:
        position.offset += sum(
            len(chunk) + 1 for chunk in section.chunks[: position.chunk]
        )
        position.chunk = 0
    text = book_section_text(section)
    if position.offset > len(text):
        position.offset = 0
    return position, text


class Theme:
    NORMAL = 0
    ACCENT = 1
    CORRECT = 2
    ERROR = 3
    MUTED = 4
    WARNING = 5
    CURRENT = 6
    CURRENT_ERROR = 7
    BAR_EMPTY = 8
    BAR_0 = 9
    BAR_1 = 10
    BAR_2 = 11
    KEYBOARD_PINKY = 12
    KEYBOARD_RING = 13
    KEYBOARD_MIDDLE = 14
    KEYBOARD_INDEX = 15
    KEYBOARD_FINGER_THEMES = (
        KEYBOARD_PINKY,
        KEYBOARD_RING,
        KEYBOARD_MIDDLE,
        KEYBOARD_INDEX,
    )
    KEYBOARD_LOCKED_PINKY = 16
    KEYBOARD_LOCKED_RING = 17
    KEYBOARD_LOCKED_MIDDLE = 18
    KEYBOARD_LOCKED_INDEX = 19
    KEYBOARD_LOCKED_THEMES = (
        KEYBOARD_LOCKED_PINKY,
        KEYBOARD_LOCKED_RING,
        KEYBOARD_LOCKED_MIDDLE,
        KEYBOARD_LOCKED_INDEX,
    )

    @classmethod
    def initialize(cls) -> None:
        if not curses.has_colors():
            return
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        keyboard_backgrounds = (
            KEYBOARD_256_BACKGROUNDS
            if curses.COLORS >= 256
            else (
                curses.COLOR_MAGENTA,
                curses.COLOR_BLUE,
                curses.COLOR_GREEN,
                curses.COLOR_YELLOW,
            )
        )
        keyboard_foregrounds = (curses.COLOR_WHITE,) * KEYBOARD_FINGER_COUNT
        keyboard_locked_foregrounds = (
            (curses.COLOR_WHITE,) * KEYBOARD_FINGER_COUNT
        )
        if curses.COLORS >= 256:
            # Use dark shades of the terminal's accent families for readability.
            if curses.can_change_color():
                curses.init_color(
                    ERROR_COLOR,
                    *((channel * 1000 + 254) // 255 for channel in ERROR_RGB),
                )
                for offset, rgb in enumerate(BAR_RGBS):
                    curses.init_color(
                        BAR_COLOR_BASE + offset,
                        *((channel * 1000 + 254) // 255 for channel in rgb),
                    )
                keyboard_backgrounds = tuple(
                    KEYBOARD_COLOR_BASE + offset
                    for offset in range(len(KEYBOARD_RGBS))
                )
                for offset, rgb in enumerate(KEYBOARD_RGBS):
                    curses.init_color(
                        KEYBOARD_COLOR_BASE + offset,
                        *((channel * 1000 + 254) // 255 for channel in rgb),
                    )
            colors = {
                cls.ACCENT: (curses.COLOR_CYAN, -1),
                cls.CORRECT: (curses.COLOR_GREEN, -1),
                cls.ERROR: (ERROR_COLOR, -1),
                cls.MUTED: (curses.COLOR_WHITE, -1),
                cls.WARNING: (curses.COLOR_YELLOW, -1),
                cls.CURRENT: (curses.COLOR_CYAN, CURRENT_BACKGROUND),
                cls.CURRENT_ERROR: (ERROR_COLOR, CURRENT_BACKGROUND),
                cls.BAR_EMPTY: (curses.COLOR_WHITE, -1),
                cls.BAR_0: (BAR_COLOR_BASE, -1),
                cls.BAR_1: (BAR_COLOR_BASE + 1, -1),
                cls.BAR_2: (BAR_COLOR_BASE + 2, -1),
            }
        else:
            colors = {
                cls.ACCENT: (curses.COLOR_CYAN, -1),
                cls.CORRECT: (curses.COLOR_GREEN, -1),
                cls.ERROR: (curses.COLOR_RED, -1),
                cls.MUTED: (curses.COLOR_WHITE, -1),
                cls.WARNING: (curses.COLOR_YELLOW, -1),
                cls.CURRENT: (curses.COLOR_CYAN, curses.COLOR_BLACK),
                cls.CURRENT_ERROR: (curses.COLOR_RED, curses.COLOR_BLACK),
                cls.BAR_EMPTY: (curses.COLOR_WHITE, -1),
                cls.BAR_0: (curses.COLOR_WHITE, -1),
                cls.BAR_1: (curses.COLOR_CYAN, -1),
                cls.BAR_2: (curses.COLOR_CYAN, -1),
            }
        for finger, background in enumerate(keyboard_backgrounds):
            colors[cls.KEYBOARD_FINGER_THEMES[finger]] = (
                keyboard_foregrounds[finger],
                background,
            )
            colors[cls.KEYBOARD_LOCKED_THEMES[finger]] = (
                keyboard_locked_foregrounds[finger],
                background,
            )
        for pair, (foreground, background) in colors.items():
            try:
                curses.init_pair(pair, foreground, background)
            except curses.error:
                curses.init_pair(pair, foreground, curses.COLOR_BLACK)


def attr(pair: int, extra: int = 0) -> int:
    return (curses.color_pair(pair) if curses.has_colors() else 0) | extra


def safe_addstr(window: curses.window, y: int, x: int, text: str, style: int = 0) -> None:
    height, width = window.getmaxyx()
    if 0 <= y < height and x < width and text:
        try:
            window.addnstr(y, max(0, x), text[max(0, -x) :], max(0, width - max(0, x) - 1), style)
        except curses.error:
            pass


def centered_text_y(height: int, line_count: int) -> int:
    return max(4, (height - line_count) // 2)


def practice_text_width(terminal_width: int) -> int:
    return min(72, terminal_width - 8)


def book_text_width(_terminal_width: int) -> int:
    return min(BOOK_LINE_WIDTH, _terminal_width - 8)


def cycle_option(
    mode: str,
    word_package: str,
    book: str,
    option: str,
    direction: int,
) -> tuple[str, str, str]:
    if option == "mode":
        mode = MODES[(MODES.index(mode) + direction) % len(MODES)]
    elif mode == "practice":
        packages = tuple(WORD_PACKAGES)
        word_package = packages[
            (packages.index(word_package) + direction) % len(packages)
        ]
    else:
        books = tuple(BOOK_PATHS)
        book = books[(books.index(book) + direction) % len(books)]
    return mode, word_package, book


def change_target_wpm(target_wpm: int, direction: int) -> int:
    return max(
        MIN_TARGET_WPM,
        min(MAX_TARGET_WPM, target_wpm + direction * TARGET_WPM_STEP),
    )


ACCENT_BASE_KEYS = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
COMPOSED_BASE_KEYS = {**ACCENT_BASE_KEYS, "ñ": "n"}


def keyboard_focus_keys(focus: str | None) -> set[str]:
    if not focus:
        return set()
    base = focus.lower()
    keys = {base}
    keys.update(
        {
            ACCENT_BASE_KEYS.get(base, ""),
            "¨" if base == "ü" else "´" if base in ACCENT_BASE_KEYS else "",
        }
        - {""}
    )
    return keys


def draw_keyboard_layout(
    stdscr: curses.window,
    progress: Progress,
    focus: str | None,
    start_y: int,
) -> None:
    _, width = stdscr.getmaxyx()
    active_keys = set(progress.active_keys)
    language = (
        progress.keyboard_language
        if progress.keyboard_language in KEYBOARD_LANGUAGES
        else DEFAULT_KEYBOARD_LANGUAGE
    )
    rows = KEYBOARD_ROWS[language]
    fingers = KEYBOARD_FINGER_BY_KEY[language]
    layout_keys = {letter for row in rows for letter in row}
    display_focus_keys = keyboard_focus_keys(focus)
    if focus is not None and not display_focus_keys & layout_keys:
        base = COMPOSED_BASE_KEYS.get(focus.lower())
        if base in layout_keys:
            display_focus_keys.add(base)
    shift_focus = focus is not None and focus.isupper()
    keyboard_width = len(rows[0]) * 3 + KEYBOARD_HAND_GAP
    keyboard_x = (width - keyboard_width) // 2
    for row_index, (row, indent) in enumerate(zip(rows, (0, 1, 2))):
        for index, letter in enumerate(row):
            if letter in ",.'":
                unlocked = letter in active_keys
            else:
                unlocked = not letter.isalpha() or letter in active_keys
            if letter in display_focus_keys:
                extra = curses.A_BOLD
                unlocked = True
            elif not unlocked:
                extra = curses.A_DIM
            else:
                extra = curses.A_BOLD
            finger = fingers[letter]
            theme = (
                Theme.KEYBOARD_FINGER_THEMES[finger]
                if unlocked
                else Theme.KEYBOARD_LOCKED_THEMES[finger]
            )
            label = f" {letter} "
            if letter in display_focus_keys:
                label = f"[{letter}]"
                base = focus.lower() if focus is not None else ""
                if shift_focus and letter == COMPOSED_BASE_KEYS.get(base, base):
                    label = f"[{focus}]"
            safe_addstr(
                stdscr,
                start_y + row_index,
                keyboard_x
                + indent
                + index * 3
                + (KEYBOARD_HAND_GAP if index >= 5 else 0),
                label,
                attr(theme, extra),
            )


def choose_options(
    stdscr: curses.window,
    progress: Progress,
) -> tuple[str, str, str, int, str, str, str]:
    mode = progress.mode
    word_package = progress.word_package
    book = progress.selected_book
    target_wpm = progress.target_wpm
    keyboard_view = (
        progress.keyboard_view
        if progress.keyboard_view in KEYBOARD_VIEWS
        else DEFAULT_KEYBOARD_VIEW
    )
    ui_language = (
        progress.ui_language
        if progress.ui_language in UI_LANGUAGES
        else DEFAULT_UI_LANGUAGE
    )
    keyboard_language = (
        progress.keyboard_language
        if progress.keyboard_language in KEYBOARD_LANGUAGES
        else DEFAULT_KEYBOARD_LANGUAGE
    )
    selected = 0
    while True:
        set_ui_language(ui_language)
        rows = ["language", "keyboard_language", "mode", "source"]
        if mode == "practice":
            rows.extend(("target", "keyboard"))
        selected = min(selected, len(rows) - 1)
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        if height < 10 or width < 42:
            message = translate("terminal.too_small")
            safe_addstr(
                stdscr,
                height // 2,
                max(0, (width - len(message)) // 2),
                message,
                attr(Theme.WARNING, curses.A_BOLD),
            )
        else:
            safe_addstr(
                stdscr,
                2,
                4,
                translate("options.title"),
                attr(Theme.ACCENT, curses.A_BOLD),
            )
            values: list[tuple[str, str]] = []
            for row in rows:
                if row == "language":
                    values.append(
                        (
                            translate("options.language"),
                            UI_LANGUAGE_LABELS[ui_language],
                        )
                    )
                elif row == "keyboard_language":
                    values.append(
                        (
                            translate("options.keyboard"),
                            KEYBOARD_LANGUAGE_LABELS[keyboard_language],
                        )
                    )
                elif row == "mode":
                    values.append(
                        (translate("options.mode"), translate(f"mode.{mode}"))
                    )
                elif row == "source":
                    source = (
                        translate(f"package.{word_package}")
                        if mode == "practice"
                        else BOOK_LABELS[book]
                    )
                    values.append((translate("options.source"), source))
                elif row == "target":
                    values.append(
                        (
                            translate("options.target"),
                            f"{target_wpm} {translate('unit.wpm')}",
                        )
                    )
                else:
                    values.append(
                        (
                            translate("options.keyboard_view"),
                            translate(f"view.{keyboard_view}"),
                        )
                    )
            row_step = 2 if height >= len(rows) * 2 + 3 else 1
            start_y = max(4, (height - len(rows) * row_step) // 2)
            start_y = min(
                start_y,
                height - 1 - (len(rows) - 1) * row_step,
            )
            for index, (label, value) in enumerate(values):
                is_selected = index == selected
                marker = "›" if is_selected else " "
                style = attr(
                    Theme.ACCENT if is_selected else Theme.MUTED,
                    curses.A_BOLD if is_selected else 0,
                )
                safe_addstr(
                    stdscr,
                    start_y + index * row_step,
                    6,
                    f"{marker} {label:<13} {value}",
                    style,
                )
        stdscr.refresh()
        key = stdscr.get_wch()
        if key == "\x03":
            raise KeyboardInterrupt
        if key == "\x1b":
            set_ui_language(progress.ui_language)
            return (
                progress.mode,
                progress.word_package,
                progress.selected_book,
                progress.target_wpm,
                progress.keyboard_view,
                progress.ui_language,
                progress.keyboard_language,
            )
        if key in (curses.KEY_UP, "k"):
            selected = (selected - 1) % len(rows)
        elif key in (curses.KEY_DOWN, "j"):
            selected = (selected + 1) % len(rows)
        elif key in (curses.KEY_LEFT, curses.KEY_RIGHT, "h", "l", " "):
            direction = -1 if key in (curses.KEY_LEFT, "h") else 1
            row = rows[selected]
            if row == "language":
                ui_language = UI_LANGUAGES[
                    (UI_LANGUAGES.index(ui_language) + direction)
                    % len(UI_LANGUAGES)
                ]
            elif row == "keyboard_language":
                keyboard_language = KEYBOARD_LANGUAGES[
                    (KEYBOARD_LANGUAGES.index(keyboard_language) + direction)
                    % len(KEYBOARD_LANGUAGES)
                ]
            elif row == "target":
                target_wpm = change_target_wpm(target_wpm, direction)
            elif row == "keyboard":
                keyboard_view = KEYBOARD_VIEWS[
                    (KEYBOARD_VIEWS.index(keyboard_view) + direction)
                    % len(KEYBOARD_VIEWS)
                ]
            else:
                mode, word_package, book = cycle_option(
                    mode,
                    word_package,
                    book,
                    row,
                    direction,
                )
        elif key in ("\n", "\r", curses.KEY_ENTER):
            return (
                mode,
                word_package,
                book,
                target_wpm,
                keyboard_view,
                ui_language,
                keyboard_language,
            )


def draw(
    stdscr: curses.window,
    session: Session,
    notice: str = "",
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    progress = session.progress
    set_ui_language(progress.ui_language)
    if height < 10 or width < 42:
        message = translate("terminal.too_small")
        safe_addstr(stdscr, height // 2, max(0, (width - len(message)) // 2), message, attr(Theme.WARNING, curses.A_BOLD))
        stdscr.refresh()
        return

    focus = session.focus
    if progress.keyboard_view == "keyboard":
        panel_y = height - 4
        draw_keyboard_layout(stdscr, progress, focus, panel_y)
    else:
        panel_y = height - 3
        bar_keys = progress.active_keys
        if focus is not None and focus in ",.'":
            bar_keys = "".join(key for key in bar_keys if key in ",.'")
        elif focus is not None and focus.isupper():
            bar_keys = "".join(key for key in bar_keys if key.isupper())
        else:
            bar_keys = "".join(key for key in bar_keys if key.islower())
        spaced_letters = " ".join(
            f"[{key}]" if key == focus else key
            for key in bar_keys
        )
        compact_letters = "".join(
            f"[{key}]" if key == focus else key
            for key in bar_keys
        )
        available = width - 6
        letters = spaced_letters if len(spaced_letters) <= available else compact_letters
        safe_addstr(stdscr, panel_y, 3, letters, attr(Theme.MUTED, curses.A_DIM))
        safe_addstr(
            stdscr,
            panel_y + 1,
            3,
            "─" * max(1, width - 6),
            attr(Theme.MUTED, curses.A_DIM),
        )

    text_width = practice_text_width(width)
    ranges = list(wrap_ranges(session.text, text_width))
    content_height = max(1, panel_y - 2)
    start_y = 1 + max(0, (content_height - len(ranges)) // 2)
    typed_count = len(session.typed)

    for row, (start, end) in enumerate(ranges):
        x = max(4, (width - (end - start)) // 2)
        for index in range(start, end):
            character = session.text[index]
            if index < typed_count:
                theme = Theme.ERROR if index in session.error_positions else Theme.CORRECT
                extra = curses.A_BOLD
                if index in session.error_positions:
                    extra |= curses.A_UNDERLINE
                style = attr(theme, extra)
                shown = character
            elif index == typed_count and session.mistake:
                style = attr(Theme.CURRENT_ERROR, curses.A_BOLD)
                shown = character
            elif index == typed_count:
                style = attr(Theme.CURRENT, curses.A_BOLD)
                shown = character
            else:
                style = attr(Theme.MUTED)
                shown = character
            safe_addstr(stdscr, start_y + row, x + index - start, shown, style)

    if notice:
        safe_addstr(
            stdscr,
            height - 1,
            3,
            notice[: max(0, width - 6)],
            attr(Theme.WARNING, curses.A_BOLD),
        )
    elif focus is not None and focus.isupper():
        hint = translate("shift")
        safe_addstr(
            stdscr,
            height - 1,
            max(0, (width - len(hint)) // 2),
            hint,
            attr(Theme.MUTED, curses.A_DIM),
        )
    stdscr.refresh()


def wrap_book_ranges(text: str, width: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        if text[start] in "\r\n":
            start += 1
            continue
        paragraph_end = start
        while paragraph_end < len(text) and text[paragraph_end] not in "\r\n":
            paragraph_end += 1
        end = min(start + width, paragraph_end)
        if end < paragraph_end:
            space = text.rfind(" ", start + 1, end + 1)
            if space > start:
                end = space + 1
        ranges.append((start, end))
        start = end
    return ranges


def book_exercise(text: str, offset: int, width: int) -> tuple[str, int]:
    offset = max(0, min(offset, len(text)))
    boundaries = book_exercise_boundaries(text, width)
    completed = bisect_right(boundaries, offset)
    end = boundaries[completed] if completed < len(boundaries) else len(text)
    return text[offset:end].rstrip(), end


@lru_cache(maxsize=64)
def book_exercise_boundaries(text: str, width: int) -> tuple[int, ...]:
    boundaries: list[int] = []
    start = 0
    minimum = width * 2
    sentence_end = re.compile(r"[.!?…]+[»”\"']?(?=\s|$)")
    for match in sentence_end.finditer(text):
        end = match.end()
        while end < len(text) and text[end].isspace():
            end += 1
        if end - start >= minimum:
            boundaries.append(end)
            start = end
    if start < len(text):
        boundaries.append(len(text))
    return tuple(boundaries)


def book_exercise_count(text: str, width: int, stop: int | None = None) -> int:
    boundaries = book_exercise_boundaries(text, width)
    if stop is None:
        return len(boundaries)
    return bisect_right(boundaries, max(0, min(stop, len(text))))


def current_book_exercise(
    progress: Progress,
    book: Book,
    width: int,
) -> tuple[BookPosition, str, int, int, int]:
    position, section_text = current_book_text(progress, book)
    boundaries = book_exercise_boundaries(section_text, width)
    if position.offset and position.offset not in boundaries:
        previous = bisect_right(boundaries, position.offset) - 1
        position.offset = boundaries[previous] if previous >= 0 else 0
    completed = bisect_right(boundaries, position.offset)
    current = min(completed + 1, max(1, len(boundaries)))
    next_offset = boundaries[current - 1] if boundaries else len(section_text)
    text = section_text[position.offset:next_offset].rstrip()
    total = len(boundaries)
    return position, text, next_offset, current, total


def visible_book_ranges(
    text: str,
    width: int,
    source_position: int,
) -> list[tuple[int, int]]:
    ranges = wrap_book_ranges(text, width)
    active_row = next(
        (
            row
            for row, (start, end) in enumerate(ranges)
            if start <= source_position < end
        ),
        next(
            (
                row
                for row, (start, _) in enumerate(ranges)
                if start > source_position
            ),
            max(0, len(ranges) - 1),
        ),
    )
    first_row = max(0, min(active_row, len(ranges) - 2))
    return ranges[first_row : first_row + 2]


def book_completion(progress: Progress, book: Book) -> float:
    position = progress.book_position(book.slug)
    if position.completed:
        return 1.0
    total = sum(len(book_section_text(section)) for section in book.sections)
    completed = sum(
        len(book_section_text(section))
        for section in book.sections[: position.section]
    ) + position.offset
    return completed / total


def draw_book(
    stdscr: curses.window,
    progress: Progress,
    book: Book,
    session: BookSession,
    notice: str = "",
    fragment_info: tuple[int, int, int] | None = None,
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    set_ui_language(progress.ui_language)
    if height < 10 or width < 42:
        message = translate("terminal.too_small")
        safe_addstr(
            stdscr,
            height // 2,
            max(0, (width - len(message)) // 2),
            message,
            attr(Theme.WARNING, curses.A_BOLD),
        )
        stdscr.refresh()
        return

    position = progress.book_position(book.slug)
    section_index, fragment_index, fragment_total = fragment_info or (
        position.section,
        position.chunk + 1,
        len(book.sections[position.section].chunks),
    )
    section = book.sections[section_index]
    metrics = (
        f"{session.wpm:>3.0f} {translate('unit.wpm')}  "
        f"{session.accuracy:>4.0%}  {book_completion(progress, book):>4.0%}"
    )
    safe_addstr(stdscr, 1, 3, book.title, attr(Theme.ACCENT, curses.A_BOLD))
    safe_addstr(stdscr, 1, width - len(metrics) - 3, metrics, curses.A_BOLD)
    section_label = (
        f"{section.title} · "
        f"{translate('book.fragment', current=fragment_index, total=fragment_total)}"
    )
    safe_addstr(stdscr, 2, 3, section_label, attr(Theme.MUTED, curses.A_DIM))
    safe_addstr(stdscr, 3, 3, "─" * max(1, width - 6), attr(Theme.MUTED, curses.A_DIM))

    text_width = book_text_width(width)
    source_position = session.source_position
    shown_ranges = visible_book_ranges(session.text, text_width, source_position)
    required = {source for source, _ in session.expected}
    completed = {source for source, _ in session.expected[: session.cursor]}
    start_y = centered_text_y(height, len(shown_ranges)) + 1

    for row, (start, end) in enumerate(shown_ranges, start=start_y):
        line = session.text[start:end]
        x = max(4, (width - len(line)) // 2)
        for index in range(start, end):
            character = session.text[index]
            if index in completed:
                theme = Theme.ERROR if index in session.error_positions else Theme.CORRECT
                extra = curses.A_BOLD
                if index in session.error_positions:
                    extra |= curses.A_UNDERLINE
                style = attr(theme, extra)
            elif index == source_position and session.mistake:
                style = attr(Theme.CURRENT_ERROR, curses.A_BOLD)
            elif index == source_position:
                style = attr(Theme.CURRENT, curses.A_BOLD)
            elif index not in required:
                style = attr(Theme.MUTED, curses.A_DIM)
            else:
                style = attr(Theme.MUTED)
            safe_addstr(stdscr, row, x + index - start, character, style)

    stats = book_level_feedback(progress)
    if notice:
        safe_addstr(
            stdscr,
            height - 2,
            3,
            notice[: max(0, width - 8)],
            attr(Theme.WARNING, curses.A_BOLD),
        )
    safe_addstr(
        stdscr,
        height - 1,
        3,
        stats,
        attr(Theme.MUTED),
    )
    stdscr.refresh()


def apply_options(stdscr: curses.window, progress: Progress) -> bool:
    previous = (
        progress.mode,
        progress.word_package,
        progress.selected_book,
        progress.target_wpm,
        progress.keyboard_view,
        progress.ui_language,
        progress.keyboard_language,
    )
    (
        mode,
        word_package,
        book,
        target_wpm,
        keyboard_view,
        ui_language,
        keyboard_language,
    ) = choose_options(stdscr, progress)
    changed = (
        mode,
        word_package,
        book,
        target_wpm,
        keyboard_view,
        ui_language,
        keyboard_language,
    ) != previous
    if not changed:
        set_ui_language(progress.ui_language)
        return False
    progress.mode = mode
    progress.word_package = word_package
    progress.selected_book = book
    progress.target_wpm = target_wpm
    progress.keyboard_view = keyboard_view
    progress.ui_language = ui_language
    progress.keyboard_language = keyboard_language
    set_ui_language(ui_language)
    if word_package != previous[1] or target_wpm != previous[3]:
        progress.reset_post_alphabet_focus()
    if word_package != previous[1]:
        select_word_package(word_package)
    save_progress(progress)
    return True


def result_fraction(actual_time_ms: float | None, target_time_ms: float) -> float:
    if actual_time_ms and actual_time_ms > 0 and target_time_ms > 0:
        return min(1.0, max(0.0, target_time_ms / actual_time_ms))
    return 0.0


def bar_for(fraction: float, length: int) -> str:
    length = max(1, length)
    fraction = min(1.0, max(0.0, fraction))
    filled = round(fraction * length * 8)
    remaining = filled
    cells: list[str] = []
    for _ in range(length):
        if remaining >= 8:
            cells.append("█")
            remaining -= 8
        elif remaining > 0:
            cells.append(PARTIAL_BLOCKS[remaining - 1])
            remaining = 0
        else:
            cells.append("░")
    return "".join(cells)


def result_gauge_value(elapsed: float) -> float:
    elapsed = max(0.0, elapsed)
    ramp = 1 - math.exp(-elapsed * 7)
    vibration = 0.009 * math.sin(elapsed * 35) + 0.004 * math.sin(elapsed * 73.5)
    return ramp * (0.96 + vibration * ramp)


def result_gauge_rows(rows: int, elapsed: float) -> list[str]:
    """Rasterize a circular dial into Braille cells, without ANSI escapes."""
    columns = rows * 2
    width, height = columns * 2, rows * 4
    bits = [[0] * columns for _ in range(rows)]
    dot_bits = ((1, 8), (2, 16), (4, 32), (64, 128))
    cx, cy = (width - 1) / 2, (height - 1) / 2
    radius = min(cx, cy) - 1

    def dot(x: float, y: float) -> None:
        ix, iy = round(x), round(y)
        if 0 <= ix < width and 0 <= iy < height:
            bits[iy // 4][ix // 2] |= dot_bits[iy % 4][ix % 2]

    def radial(angle: float, inner: float, outer: float) -> None:
        steps = max(1, math.ceil((outer - inner) * 2))
        for step in range(steps + 1):
            distance = inner + (outer - inner) * step / steps
            dot(cx + math.cos(angle) * distance, cy + math.sin(angle) * distance)

    for step in range(max(48, round(radius * 8))):
        angle = step / max(48, round(radius * 8)) * math.tau
        dot(cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)
    start, sweep = math.pi * 0.75, math.pi * 1.5
    for tick in range(13):
        radial(start + sweep * tick / 12,
               radius * (0.7 if tick % 3 == 0 else 0.82), radius)
    radial(start + sweep * result_gauge_value(elapsed), 0, radius * 0.7)
    return ["".join(chr(0x2800 + cell) if cell else " " for cell in row) for row in bits]


def draw_result(
    stdscr: curses.window,
    session: Session,
    progress: Progress,
    unlocked: list[str],
    hi_score: bool,
    ticks: int,
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    set_ui_language(progress.ui_language)
    if height < 10 or width < 42:
        message = translate("terminal.too_small")
        safe_addstr(
            stdscr,
            height // 2,
            max(0, (width - len(message)) // 2),
            message,
            attr(Theme.WARNING, curses.A_BOLD),
        )
        stdscr.refresh()
        return

    target = progress.target_time_ms
    focus = None if progress.keys_complete else session.focus
    start_y = max(2, (height - 9) // 2)
    elapsed_ms = ticks * RESULT_FRAME_MS
    celebrate = bool(unlocked or hi_score)
    column_width = 10
    gauge_height = 0
    if celebrate:
        gauge_height = min(height - 2, (width - 1) // 2)
        gauge_width = gauge_height * 2
        gauge_x = min(
            width - gauge_width - 1,
            max(0, round(width * 0.75 - gauge_width / 2)),
        )
        gauge_y = (height - gauge_height) // 2
        focus_y = start_y - 1
    else:
        focus_y = start_y

    title: str | None = None
    blink = False
    if unlocked:
        if progress.keys_complete:
            title = translate("result.title.mastery")
        elif alphabet_complete(progress.active_keys) and any(
            key.islower() for key in unlocked
        ):
            title = translate("result.title.alphabet")
        elif (
            alphabet_complete(progress.active_keys)
            and any(key.isupper() for key in unlocked)
            and session.focus is not None
            and session.focus.islower()
        ):
            title = translate("result.title.capitals")
        elif (
            capitals_complete(progress.active_keys)
            and any(key in ",.'" for key in unlocked)
            and session.focus is not None
            and session.focus.isupper()
        ):
            title = translate("result.title.marks")
        elif unlocked[0].isupper():
            title = translate("result.title.new_capital")
        elif unlocked[0] in ",.'":
            title = translate("result.title.new_mark")
        else:
            title = translate("result.title.new_letter")
        blink = True
    elif hi_score:
        title = translate("result.title.new_record")
        blink = True
    elif progress.keys_complete:
        title = translate("result.title.mastery")

    if progress.keys_complete:
        current_wpm = session.wpm
        best_wpm = progress.best_wpm
        animated_current_wpm = min(
            current_wpm,
            elapsed_ms // RESULT_WPM_MS_PER_UNIT,
        )
        animated_best_wpm = min(
            best_wpm,
            elapsed_ms // RESULT_WPM_MS_PER_UNIT,
        )
        animated_target_wpm = min(
            progress.target_wpm,
            elapsed_ms // RESULT_WPM_MS_PER_UNIT,
        )
        labels = (
            translate("result.current"),
            translate("result.best"),
            translate("result.target"),
        )
        unit = translate("unit.wpm")
        values = (
            f"{animated_current_wpm:03.0f} {unit}",
            f"{animated_best_wpm:03.0f} {unit}",
            f"{animated_target_wpm:03d} {unit}",
        )
    elif focus is None:
        current_ms = 0
        best_ms = 0
        animated_current_ms = 0
        animated_best_ms = 0
        animated_target_ms = min(
            round(target), elapsed_ms // RESULT_COUNT_MS_PER_UNIT
        )
        labels = (
            translate("result.current"),
            translate("result.best"),
            translate("result.target"),
        )
        unit = translate("result.unit_ms")
        values = (
            f"{animated_current_ms:03d} {unit}",
            f"{animated_best_ms:03d} {unit}",
            f"{animated_target_ms:03d} {unit}",
        )
    else:
        stat = progress.stat(focus)
        current_ms = round(stat.time_ms or 0)
        best_ms = round(stat.best_time_ms or 0)
        animated_current_ms = min(current_ms, elapsed_ms // RESULT_COUNT_MS_PER_UNIT)
        animated_best_ms = min(best_ms, elapsed_ms // RESULT_COUNT_MS_PER_UNIT)
        animated_target_ms = min(round(target), elapsed_ms // RESULT_COUNT_MS_PER_UNIT)
        labels = (
            translate("result.current"),
            translate("result.best"),
            translate("result.target"),
        )
        unit = translate("result.unit_ms")
        values = (
            f"{animated_current_ms:03d} {unit}",
            f"{animated_best_ms:03d} {unit}",
            f"{animated_target_ms:03d} {unit}",
        )

    if celebrate:
        for row, text in enumerate(result_gauge_rows(gauge_height, elapsed_ms / 1000)):
            safe_addstr(
                stdscr,
                gauge_y + row,
                gauge_x,
                text,
                attr(Theme.ACCENT, curses.A_DIM),
            )

    if focus is not None:
        safe_addstr(
            stdscr,
            focus_y,
            max(0, (width - 3) // 2),
            f"[{focus}]",
            attr(Theme.ACCENT, curses.A_BOLD),
        )

    inner_width = column_width * len(labels) + 6
    box_x = max(1, (width - inner_width - 2) // 2)
    box_y = start_y + 2
    top = "┌" + "─" * inner_width + "┐"
    label_content = "  ".join(f"{label:^{column_width}}" for label in labels)
    value_content = "  ".join(f"{value:^{column_width}}" for value in values)
    bottom = "└" + "─" * inner_width + "┘"
    safe_addstr(
        stdscr,
        box_y,
        box_x,
        top,
        attr(Theme.MUTED),
    )
    for row, content, style in (
        (box_y + 1, label_content, attr(Theme.MUTED, curses.A_DIM)),
        (box_y + 2, value_content, attr(Theme.ACCENT, curses.A_BOLD)),
    ):
        safe_addstr(stdscr, row, box_x, "│", attr(Theme.MUTED))
        safe_addstr(stdscr, row, box_x + 1, " ", attr(Theme.MUTED))
        safe_addstr(stdscr, row, box_x + 2, content, style)
        safe_addstr(stdscr, row, box_x + 2 + len(content), " ", attr(Theme.MUTED))
        safe_addstr(
            stdscr,
            row,
            box_x + 3 + len(content),
            "│",
            attr(Theme.MUTED),
        )
    safe_addstr(stdscr, box_y + 3, box_x, bottom, attr(Theme.MUTED))

    if not progress.keys_complete:
        timing_label = translate("result.ms_keystroke")
        if focus is not None:
            cost = progress.key_cost(focus)
            raw_ms = progress.stat(focus).raw_time_ms
            if cost > 1:
                total = f"{raw_ms:.0f}" if raw_ms is not None else "--"
                timing_label += f" · {total} ms total / {cost}"
        safe_addstr(
            stdscr, box_y + 4, max(0, (width - len(timing_label)) // 2),
            timing_label, attr(Theme.MUTED),
        )

    if title is not None and (not blink or (ticks // 8) % 2 == 0):
        safe_addstr(
            stdscr,
            box_y + 5,
            max(0, (width - len(title)) // 2),
            title,
            attr(Theme.WARNING if blink else Theme.ACCENT, curses.A_BOLD),
        )

    stdscr.refresh()


def run_result(
    stdscr: curses.window,
    session: Session,
    progress: Progress,
    unlocked: list[str],
    hi_score: bool,
) -> str:
    try:
        stdscr.timeout(RESULT_FRAME_MS)
        ticks = 0
        while True:
            draw_result(stdscr, session, progress, unlocked, hi_score, ticks)
            ticks += 1
            try:
                key = stdscr.get_wch()
            except curses.error:
                continue
            if key == "\x03":
                return "exit"
            if key == "\x1b":
                stdscr.timeout(-1)
                apply_options(stdscr, progress)
                return "next"
            if key in ("\n", "\r", curses.KEY_ENTER):
                return "next"
    finally:
        stdscr.timeout(-1)


def run_practice_session(stdscr: curses.window, progress: Progress) -> str:
    set_ui_language(progress.ui_language)
    session = Session(progress, generate_lesson(progress))
    previous_keys = set(progress.active_keys)
    notice = ""
    while not session.complete:
        draw(stdscr, session, notice)
        notice = ""
        try:
            key = stdscr.get_wch()
        except curses.error:
            continue
        if key == "\x03":
            save_progress(progress)
            return "exit"
        if key == "\x1b":
            apply_options(stdscr, progress)
            return "switch"
        if key in ("\b", "\x7f", curses.KEY_BACKSPACE):
            session.reset()
            notice = translate("restart.exercise")
        elif isinstance(key, str) and key.isprintable():
            session.add(key)

    previous_best = (
        progress.stat(session.focus).best_time_ms if session.focus else None
    )
    session_wpm = session.wpm
    previous_best_wpm = progress.best_wpm
    session.commit()
    progress.record_lesson_focus(session.focus)
    if progress.keys_complete:
        progress.record_wpm(session_wpm)
    unlocked = [
        key for key in progress.active_keys if key not in previous_keys
    ]
    hi_score = False
    if session.focus:
        current_best = progress.stat(session.focus).best_time_ms
        hi_score = (
            previous_best is not None
            and current_best is not None
            and current_best < previous_best
        )
    if progress.keys_complete and session_wpm > previous_best_wpm:
        hi_score = True
    save_progress(progress)
    return run_result(stdscr, session, progress, unlocked, hi_score)


def draw_finished_book(
    stdscr: curses.window,
    progress: Progress,
    book: Book,
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    set_ui_language(progress.ui_language)
    if height < 10 or width < 42:
        message = translate("terminal.too_small")
        safe_addstr(
            stdscr,
            height // 2,
            max(0, (width - len(message)) // 2),
            message,
            attr(Theme.WARNING, curses.A_BOLD),
        )
    else:
        title = translate("book.completed", title=book.title)
        safe_addstr(
            stdscr,
            height // 2 - 1,
            max(3, (width - len(title)) // 2),
            title,
            attr(Theme.CORRECT, curses.A_BOLD),
        )
    stdscr.refresh()


def run_finished_book(stdscr: curses.window, progress: Progress, book: Book) -> str:
    while True:
        draw_finished_book(stdscr, progress, book)
        key = stdscr.get_wch()
        if key == "\x03":
            return "exit"
        if key == "\x1b":
            apply_options(stdscr, progress)
            return "next"
        if key in ("r", "R"):
            progress.books[book.slug] = BookPosition()
            save_progress(progress)
            return "next"


def run_book_session(stdscr: curses.window, progress: Progress) -> str:
    set_ui_language(progress.ui_language)
    book = load_book(progress.selected_book)
    position, _ = current_book_chunk(progress, book)
    if position.completed:
        return run_finished_book(stdscr, progress, book)
    _, terminal_width = stdscr.getmaxyx()
    position, text, next_offset, fragment_index, fragment_total = (
        current_book_exercise(progress, book, book_text_width(terminal_width))
    )
    fragment_info = (position.section, fragment_index, fragment_total)
    session = BookSession(text, progress.book_level)
    notice = ""
    while not session.complete:
        draw_book(
            stdscr,
            progress,
            book,
            session,
            notice,
            fragment_info=fragment_info,
        )
        notice = ""
        try:
            key = stdscr.get_wch()
        except curses.error:
            continue
        if key == "\x03":
            save_progress(progress)
            return "exit"
        if key == "\x1b":
            apply_options(stdscr, progress)
            return "switch"
        if key in ("\b", "\x7f", curses.KEY_BACKSPACE):
            session.reset()
            notice = translate("restart.fragment")
        elif key in ("\n", "\r", curses.KEY_ENTER):
            session.add("\n")
        elif isinstance(key, str) and key.isprintable():
            session.add(key)

    record_book_session(progress, session)
    advance_book_position(progress, book, next_offset)
    save_progress(progress)
    while True:
        draw_book(
            stdscr,
            progress,
            book,
            session,
            fragment_info=fragment_info,
        )
        key = stdscr.get_wch()
        if key == "\x03":
            return "exit"
        if key == "\x1b":
            apply_options(stdscr, progress)
            return "next"
        if key in ("\n", "\r", curses.KEY_ENTER):
            return "next"


def run(stdscr: curses.window, progress: Progress) -> None:
    curses.curs_set(0)
    if "ESCDELAY" not in os.environ:
        curses.set_escdelay(DEFAULT_ESC_DELAY_MS)
    stdscr.keypad(True)
    Theme.initialize()
    while True:
        result = (
            run_practice_session(stdscr, progress)
            if progress.mode == "practice"
            else run_book_session(stdscr, progress)
        )
        if result == "exit":
            return


def parse_key_cost(value: str) -> tuple[str, int]:
    try:
        character, count = value.rsplit("=", 1)
        cost = int(count)
        Progress().set_key_cost(character, cost)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(
            "usa CARÁCTER=N, con un carácter imprimible y N entre 1 y 10"
        ) from None
    return character, cost


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="borra el progreso guardado antes de iniciar",
    )
    parser.add_argument(
        "--words",
        choices=WORD_PACKAGES,
        help="cambia y guarda el paquete de palabras",
    )
    parser.add_argument(
        "--key-cost",
        action="append",
        type=parse_key_cost,
        default=[],
        metavar="CARÁCTER=N",
        help="guarda las pulsaciones necesarias para un carácter; se puede repetir",
    )
    args = parser.parse_args()
    locale.setlocale(locale.LC_ALL, "")
    path = data_path()
    if args.reset:
        path.unlink(missing_ok=True)
    progress = load_progress(path)
    set_ui_language(progress.ui_language)
    for character, cost in args.key_cost:
        progress.set_key_cost(character, cost)
    if args.words is not None:
        progress.word_package = args.words
    select_word_package(progress.word_package)
    if args.key_cost:
        save_progress(progress, path)
    try:
        curses.wrapper(run, progress)
    except KeyboardInterrupt:
        save_progress(progress, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
