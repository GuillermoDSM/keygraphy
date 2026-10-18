import json
import argparse
import random
import tempfile
import unittest
import unicodedata
from pathlib import Path
from unittest.mock import Mock, patch

import keygraphy

from keygraphy import (
    BOOK_LEVEL_MIN_ATTEMPTS,
    BOOK_LEVELS,
    BOOK_LINE_WIDTH,
    Book,
    BookPosition,
    BookSection,
    BookSession,
    INITIAL_LETTERS,
    KEYBOARD_FINGER_BY_KEY,
    KEYBOARD_ROWS,
    KEY_ORDER,
    LETTER_ORDER,
    LetterStat,
    Progress,
    Session,
    Theme,
    WORDS,
    WORD_PACKAGES,
    advance_book_position,
    apply_options,
    available_contractions,
    bar_for,
    book_exercise,
    book_exercise_boundaries,
    book_expected_positions,
    book_section_text,
    book_text_width,
    build_word_pool,
    change_target_wpm,
    centered_text_y,
    current_book_chunk,
    current_book_exercise,
    cycle_option,
    choose_options,
    draw_book,
    draw,
    draw_keyboard_layout,
    draw_result,
    eligible_words,
    generate_lesson,
    load_book,
    load_progress,
    load_word_list,
    main,
    practice_text_width,
    parse_key_cost,
    record_book_session,
    result_fraction,
    run,
    run_book_session,
    run_practice_session,
    run_result,
    save_progress,
    select_word_package,
    unlock_feedback,
    visible_book_ranges,
    wrap_book_ranges,
    wrap_ranges,
)


def master_keys(progress: Progress, keys: str = KEY_ORDER) -> None:
    for key in keys:
        progress.letters[key] = LetterStat(time_ms=200, best_time_ms=200)


class ProgressTests(unittest.TestCase):
    def test_new_progress_defaults_to_keyboard_view(self):
        self.assertEqual(Progress().keyboard_view, "keyboard")

    def test_result_fraction_measures_closeness_to_target(self):
        self.assertEqual(result_fraction(343, 343), 1.0)
        self.assertEqual(result_fraction(686, 343), 0.5)
        self.assertAlmostEqual(result_fraction(1715, 343), 0.2)
        self.assertEqual(result_fraction(None, 343), 0.0)
        self.assertEqual(result_fraction(0, 343), 0.0)

    def test_bar_for_uses_partial_blocks_for_fine_grain(self):
        self.assertEqual(bar_for(0.0, 10), "░" * 10)
        self.assertEqual(bar_for(1.0, 10), "█" * 10)
        bar = bar_for(0.25, 10)
        self.assertEqual(len(bar), 10)
        self.assertEqual(bar.count("█"), 2)
        self.assertEqual(bar[2], "▌")
        self.assertEqual(bar[3], "░")

    def test_uses_bundled_corpus_frequency_order(self):
        self.assertEqual(LETTER_ORDER, "eaosnirldctumpgbvóqfhíájzéyxñúkwü")

    def test_starts_with_six_letters_and_focuses_unsampled_letter(self):
        progress = Progress()
        self.assertEqual(progress.active_keys, LETTER_ORDER[:INITIAL_LETTERS])
        self.assertEqual(progress.weakest_key(), LETTER_ORDER[0])

    def test_includes_next_letter_when_every_active_letter_reached_target(self):
        progress = Progress()
        for letter in progress.active_keys:
            progress.letters[letter] = LetterStat(
                hits=30,
                misses=0,
                time_ms=200,
                best_time_ms=200,
            )
        self.assertEqual(progress.active_keys, LETTER_ORDER[: INITIAL_LETTERS + 1])
        self.assertEqual(progress.weakest_key(), LETTER_ORDER[INITIAL_LETTERS])

    def test_accuracy_does_not_block_progress(self):
        progress = Progress()
        for letter in progress.active_keys:
            progress.letters[letter] = LetterStat(
                hits=1,
                misses=20,
                time_ms=200,
                best_time_ms=200,
            )
        self.assertEqual(progress.active_keys, LETTER_ORDER[: INITIAL_LETTERS + 1])

    def test_new_letter_remains_focused_until_it_reaches_target(self):
        progress = Progress()
        for letter in LETTER_ORDER[:INITIAL_LETTERS]:
            progress.letters[letter] = LetterStat(
                time_ms=200,
                best_time_ms=200,
            )
        new_letter = LETTER_ORDER[INITIAL_LETTERS]
        progress.stat(new_letter).append_lesson(20, 4, 500)
        self.assertEqual(progress.weakest_key(), new_letter)
        self.assertEqual(progress.active_keys, LETTER_ORDER[: INITIAL_LETTERS + 1])

    def test_current_slowdown_does_not_refocus_a_mastered_letter(self):
        progress = Progress()
        for letter in LETTER_ORDER[:INITIAL_LETTERS]:
            progress.letters[letter] = LetterStat(
                time_ms=200,
                best_time_ms=200,
            )
        progress.letters["e"].time_ms = 500
        self.assertEqual(progress.weakest_key(), LETTER_ORDER[INITIAL_LETTERS])

    def test_completed_keys_focuses_the_slowest_current_key(self):
        progress = Progress()
        master_keys(progress)
        slowest = KEY_ORDER[-1]
        progress.letters[slowest].time_ms = 500

        self.assertTrue(progress.keys_complete)
        self.assertEqual(progress.weakest_key(), slowest)

    def test_completed_keys_keeps_focus_for_three_lessons(self):
        progress = Progress()
        master_keys(progress)
        first = KEY_ORDER[-1]
        second = KEY_ORDER[-2]
        progress.letters[first].time_ms = 500
        progress.letters[second].time_ms = 450

        for _ in range(3):
            self.assertEqual(progress.lesson_focus(), first)
            progress.record_lesson_focus(first)
        progress.letters[second].time_ms = 600

        self.assertEqual(progress.lesson_focus(), second)

    def test_best_wpm_is_kept_per_word_package(self):
        progress = Progress()
        progress.record_wpm(42)
        progress.word_package = "en-us"

        self.assertEqual(progress.best_wpm, 0.0)
        progress.record_wpm(51)
        progress.word_package = "es-la"
        self.assertEqual(progress.best_wpm, 42)

    def test_speed_uses_lesson_smoothing_and_keeps_the_best(self):
        stat = LetterStat()
        stat.append_lesson(10, 0, 400)
        stat.append_lesson(10, 0, 200)
        self.assertAlmostEqual(stat.time_ms, 380)
        self.assertAlmostEqual(stat.best_time_ms, 380)
        stat.append_lesson(10, 0, 500)
        self.assertAlmostEqual(stat.time_ms, 392)
        self.assertAlmostEqual(stat.best_time_ms, 380)

    def test_unlock_feedback_explains_the_weakest_key(self):
        progress = Progress()
        feedback = unlock_feedback(progress)
        self.assertNotIn("Foco", feedback)
        self.assertIn("actual -- ms", feedback)
        self.assertIn("mejor -- ms", feedback)
        self.assertIn("objetivo 343 ms", feedback)

    def test_unlock_feedback_reports_completed_keys(self):
        progress = Progress()
        master_keys(progress)
        self.assertEqual(unlock_feedback(progress), "Todas las teclas dominadas")

    def test_capitals_unlock_after_every_lowercase_letter(self):
        progress = Progress()
        master_keys(progress, LETTER_ORDER)
        self.assertFalse(progress.keys_complete)
        self.assertEqual(progress.active_keys, LETTER_ORDER + "E")
        self.assertEqual(progress.weakest_key(), "E")

    def test_capital_key_cost_adds_one_press_for_shift(self):
        progress = Progress()
        self.assertEqual(progress.key_cost("E"), 2)
        self.assertEqual(progress.key_cost("Ó"), 3)
        self.assertEqual(progress.key_cost("Ñ"), 2)

    def test_signs_unlock_after_capitals_and_period_comes_first(self):
        progress = Progress()
        master_keys(progress, KEY_ORDER[:-2])
        self.assertFalse(progress.keys_complete)
        self.assertEqual(progress.active_keys, KEY_ORDER[:-1])
        self.assertEqual(progress.weakest_key(), ".")
        self.assertEqual(KEY_ORDER[-2:], ".,")


class LessonTests(unittest.TestCase):
    def test_corpus_has_ten_thousand_frequency_ordered_words(self):
        self.assertEqual(len(WORDS), 10_000)
        self.assertEqual(WORDS[:5], ("de", "la", "en", "el", "que"))

    def test_spanish_package_is_available(self):
        words = load_word_list(WORD_PACKAGES["es-la"])
        self.assertEqual(len(words), 10_000)
        self.assertEqual(words[:5], ("de", "la", "en", "el", "que"))

    def test_english_package_is_available(self):
        words = load_word_list(WORD_PACKAGES["en-us"])
        self.assertEqual(len(words), 10_000)
        self.assertEqual(words[:5], ("the", "to", "and", "of", "in"))

    def test_filter_preserves_frequency_order(self):
        eligible, focused = eligible_words("eaosrn", "e")
        self.assertEqual(eligible[:5], ["en", "se", "es", "no", "son"])
        self.assertTrue(all("e" in word for word in focused))

    def test_small_word_pool_is_filled_with_pseudowords(self):
        pool = build_word_pool("ea", "e", random.Random(2))
        self.assertEqual(len(pool), 15)
        self.assertTrue(all(set(word) <= set("ea") for word in pool))
        self.assertTrue(all("e" in word for word in pool))

    def test_completed_alphabet_pool_balances_focused_and_general_words(self):
        pool = build_word_pool(LETTER_ORDER, "a", random.Random(2), minimum=20)
        focused = sum("a" in word for word in pool)

        self.assertGreater(focused, 0)
        self.assertAlmostEqual(focused / len(pool), 0.5, delta=0.05)

    def test_lesson_uses_only_active_keys_and_spaces(self):
        progress = Progress()
        lesson = generate_lesson(progress, random.Random(4), target_length=80)
        self.assertGreaterEqual(len(lesson), 80)
        self.assertLessEqual(set(lesson), set(progress.active_keys + " "))
        self.assertIn(progress.weakest_key(), lesson)

    def test_capital_lesson_capitalizes_only_focus_starts(self):
        progress = Progress()
        master_keys(progress, LETTER_ORDER)
        self.assertEqual(progress.lesson_focus(), "E")
        lesson = generate_lesson(progress, random.Random(6), target_length=120)
        self.assertEqual({key for key in lesson if key.isupper()}, {"E"})
        tokens = lesson.split(" ")
        starters = sum(token.startswith("E") for token in tokens)
        self.assertGreaterEqual(starters, len(tokens) // 3)
        self.assertLessEqual(starters, len(tokens) * 2 // 3 + 1)
        for token in tokens:
            if not token.startswith("E"):
                self.assertFalse(token[0].isupper())

    def test_capital_lesson_fills_missing_starters_with_pseudo_words(self):
        progress = Progress()
        index = KEY_ORDER.index("Ü")
        master_keys(progress, KEY_ORDER[:index])
        self.assertEqual(progress.lesson_focus(), "Ü")
        lesson = generate_lesson(progress, random.Random(5), target_length=120)
        self.assertEqual({key for key in lesson if key.isupper()}, {"Ü"})
        tokens = lesson.split(" ")
        starters = sum(token.startswith("Ü") for token in tokens)
        self.assertGreaterEqual(starters, len(tokens) // 3)

    def test_period_lesson_marks_and_capitalizes_sentences(self):
        progress = Progress()
        master_keys(progress, KEY_ORDER[:-2])
        self.assertEqual(progress.lesson_focus(), ".")
        lesson = generate_lesson(progress, random.Random(9), target_length=160)
        tokens = lesson.split(" ")
        marked = [token for token in tokens if token.endswith(".")]
        self.assertGreaterEqual(len(marked), len(tokens) // 6)
        self.assertTrue(tokens[0][0].isupper())
        self.assertNotIn("'", lesson)
        self.assertNotIn(",", lesson)
        for previous, current in zip(tokens, tokens[1:]):
            if previous.endswith("."):
                self.assertTrue(current[0].isupper())
            else:
                self.assertFalse(current[0].isupper())

    def test_comma_lesson_keeps_reviewing_periods(self):
        progress = Progress()
        master_keys(progress, KEY_ORDER[:-1])
        self.assertEqual(progress.lesson_focus(), ",")
        lesson = generate_lesson(progress, random.Random(10), target_length=200)
        tokens = lesson.split(" ")
        self.assertTrue(any(token.endswith(",") for token in tokens))
        self.assertTrue(any(token.endswith(".") for token in tokens))
        self.assertNotIn("'", lesson)

    def test_apostrophe_phase_uses_real_contractions_in_english(self):
        self.addCleanup(select_word_package, "es-la")
        select_word_package("en-us")
        order = keygraphy.KEY_ORDER
        progress = Progress(word_package="en-us")
        master_keys(progress, order[:-1])
        self.assertEqual(progress.lesson_focus(), "'")
        lesson = generate_lesson(progress, random.Random(12), target_length=220)
        tokens = lesson.split(" ")
        apostrophes = [token for token in tokens if "'" in token]
        self.assertGreaterEqual(len(apostrophes), len(tokens) // 4)
        allowed = {word.lower() for word in available_contractions(order)}
        for token in apostrophes:
            self.assertIn(token.rstrip(".,").lower(), allowed)
        self.assertTrue(any(token.endswith((".", ",")) for token in tokens))

    def test_session_records_hits_and_misses(self):
        progress = Progress()
        session = Session(progress, "era")
        session.add("e", now=1.0)
        session.add("x", now=1.2)
        self.assertFalse(session.complete)
        self.assertEqual(session.typed, ["e"])
        self.assertTrue(session.mistake)
        self.assertEqual(session.error_positions, {1})
        session.add("r", now=1.4)
        session.add("a", now=1.6)
        self.assertTrue(session.complete)
        session.commit()
        self.assertEqual(session.correct, 3)
        self.assertEqual(session.attempts, 4)
        self.assertEqual(progress.stat("e").hits, 0)
        self.assertEqual(progress.stat("r").misses, 1)
        self.assertAlmostEqual(progress.stat("a").time_ms, 200)

    def test_repeated_typos_count_as_one_miss_for_the_completed_key(self):
        progress = Progress()
        session = Session(progress, "era")
        session.add("e", now=1.0)
        session.add("x", now=1.1)
        session.add("x", now=1.2)
        session.add("r", now=1.3)
        session.add("a", now=1.5)
        session.commit()
        self.assertEqual(progress.stat("r").hits, 1)
        self.assertEqual(progress.stat("r").misses, 1)

    def test_lesson_average_is_validated_after_all_intervals_are_combined(self):
        progress = Progress()
        session = Session(progress, "eaa")
        session.add("e", now=1.0)
        session.add("a", now=1.02)
        session.add("a", now=1.12)
        session.commit()
        self.assertEqual(progress.stat("a").time_ms, 60)

    def test_session_keeps_the_focus_used_to_generate_its_lesson(self):
        progress = Progress()
        session = Session(progress, "era")
        focus = LETTER_ORDER[0]
        self.assertEqual(session.focus, focus)
        progress.letters[focus] = LetterStat(
            hits=30,
            misses=0,
            time_ms=200,
            best_time_ms=200,
        )
        self.assertEqual(progress.weakest_key(), LETTER_ORDER[1])
        self.assertEqual(session.focus, focus)

    def test_reset_discards_partial_attempt_and_statistics(self):
        progress = Progress()
        session = Session(progress, "era")
        session.add("e", now=1.0)
        session.add("x", now=1.2)
        session.reset()
        self.assertEqual(session.typed, [])
        self.assertEqual(session.attempts, 0)
        self.assertFalse(session.mistake)
        self.assertEqual(session.error_positions, set())
        self.assertEqual(progress.letters, {})

    def test_wrap_ranges_preserves_all_non_separator_characters(self):
        text = "uno dos tres cuatro"
        pieces = [text[start:end] for start, end in wrap_ranges(text, 8)]
        self.assertEqual(" ".join(pieces), text)

    def test_practice_uses_two_lines_when_terminal_is_wide(self):
        self.assertEqual(practice_text_width(100), 72)
        self.assertEqual(practice_text_width(42), 34)
        progress = Progress()
        lesson = generate_lesson(progress, random.Random(8), target_length=120)
        self.assertEqual(len(list(wrap_ranges(lesson, practice_text_width(100)))), 2)


class KeyTimingTests(unittest.TestCase):
    def test_composed_and_shifted_characters_use_physical_key_costs(self):
        progress = Progress()
        text = "aúüUÚÜ,.\'"
        session = Session(progress, text)
        now = 1.0
        session.add(text[0], now=now)
        for character in text[1:]:
            now += 0.2 * progress.key_cost(character)
            session.add(character, now=now)
        session.commit()
        for character, cost in (("ú", 2), ("ü", 3), ("U", 2), ("Ú", 3), ("Ü", 4), (",", 1), (".", 1), ("'", 1)):
            with self.subTest(character=character):
                stat = progress.stat(character)
                self.assertAlmostEqual(stat.time_ms, 200)
                self.assertAlmostEqual(stat.raw_time_ms, cost * 200)
                self.assertEqual(stat.hits, 1)
        self.assertNotIn("u", progress.letters)
        self.assertAlmostEqual(session.wpm, len(text) / 5 / ((now - 1) / 60))

    def test_normalized_timing_unlocks_the_next_letter(self):
        progress = Progress()
        focus_index = LETTER_ORDER.index("ó")
        for letter in LETTER_ORDER[:focus_index]:
            progress.letters[letter] = LetterStat(time_ms=200, best_time_ms=200)
        self.assertEqual(progress.weakest_key(), "ó")
        session = Session(progress, "aó")
        session.add("a", now=1)
        session.add("ó", now=1.6)
        session.commit()
        self.assertEqual(progress.stat("ó").time_ms, 300)
        self.assertIn(LETTER_ORDER[focus_index + 1], progress.active_keys)

    def test_capital_session_records_shifted_samples(self):
        progress = Progress()
        session = Session(progress, "nE")
        session.add("n", now=1.0)
        session.add("E", now=1.4)
        session.commit()
        stat = progress.stat("E")
        self.assertEqual(stat.hits, 1)
        self.assertAlmostEqual(stat.raw_time_ms, 400)
        self.assertAlmostEqual(stat.time_ms, 200)

    def test_corrected_composed_character_does_not_improve_speed(self):
        progress = Progress()
        session = Session(progress, "aüü")
        session.add("a", now=1)
        session.add("ü", now=1.6)
        session.add("x", now=1.7)
        session.add("x", now=1.8)
        session.add("ü", now=1.9)
        session.commit()
        self.assertEqual(progress.stat("ü").time_ms, 200)
        self.assertEqual(progress.stat("ü").raw_time_ms, 600)
        self.assertEqual(progress.stat("ü").misses, 1)

    def test_raw_and_normalized_smoothing_keep_best_and_survive_cost_changes(self):
        progress = Progress()
        for elapsed in (600, 300, 900):
            session = Session(progress, "aü")
            session.add("a", now=1)
            session.add("ü", now=1 + elapsed / 1000)
            session.commit()
        stat = progress.stat("ü")
        self.assertAlmostEqual(stat.raw_time_ms, 603)
        self.assertAlmostEqual(stat.time_ms, 201)
        self.assertAlmostEqual(stat.best_time_ms, 190)
        progress.set_key_cost("ü", 2)
        self.assertAlmostEqual(stat.time_ms, 301.5)
        self.assertAlmostEqual(stat.best_time_ms, 285)
        self.assertEqual(progress.key_cost("Ü"), 3)
        progress.set_key_cost("Ü", 2)
        self.assertEqual(progress.key_cost("Ü"), 2)

    def test_short_normalized_intervals_are_not_accepted_as_speed(self):
        progress = Progress()
        session = Session(progress, "aü")
        session.add("a", now=1)
        session.add("ü", now=1.09)
        session.commit()
        self.assertIsNone(progress.stat("ü").time_ms)
        self.assertEqual(progress.stat("ü").hits, 1)

    def test_old_accent_timings_migrate_once_and_preserve_raw_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(json.dumps({"letters": {
                "ü": {"hits": 10, "time_ms": 900, "best_time_ms": 600},
                "ó": {"time_ms": 800, "best_time_ms": 600},
                "a": {"time_ms": 200, "best_time_ms": 180},
            }}), encoding="utf-8")
            progress = load_progress(path)
            self.assertEqual(progress.stat("ü").time_ms, 300)
            self.assertEqual(progress.stat("ü").best_time_ms, 200)
            self.assertEqual(progress.stat("ó").time_ms, 400)
            self.assertEqual(progress.stat("a").time_ms, 200)
            save_progress(progress, path)
            reloaded = load_progress(path)
            self.assertEqual(reloaded.letters, progress.letters)
            self.assertEqual(reloaded.stat("ü").raw_time_ms, 900)

    def test_custom_cost_and_shifted_punctuation_statistics_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            progress = Progress()
            progress.set_key_cost("ü", 2)
            session = Session(progress, "aüA,'")
            for character, now in zip(session.text, (1, 1.4, 1.8, 2, 2.2)):
                session.add(character, now=now)
            session.commit()
            save_progress(progress, path)
            loaded = load_progress(path)
            self.assertEqual(loaded.key_costs, {"ü": 2})
            self.assertEqual(loaded.letters, progress.letters)
            self.assertEqual(loaded.stat("ü").time_ms, 200)

    def test_invalid_saved_costs_do_not_discard_valid_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(json.dumps({"key_costs": {
                "ü": 2, "a": 0, "b": True, "c": 1.5, "dd": 2,
            }, "letters": {"e": {"hits": 4, "time_ms": 200}}}), encoding="utf-8")
            progress = load_progress(path)
            self.assertEqual(progress.key_costs, {"ü": 2})
            self.assertEqual(progress.stat("e").hits, 4)

    def test_cli_cost_parser_accepts_overrides_and_rejects_invalid_values(self):
        self.assertEqual(parse_key_cost("ü=2"), ("ü", 2))
        self.assertEqual(parse_key_cost("==2"), ("=", 2))
        for value in ("ü", "ü=0", "ü=-1", "ü=11", "ü=1.5", "ab=2", "=2"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                parse_key_cost(value)

    def test_cli_saves_cost_before_starting_and_reuses_it_on_next_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            with (
                patch("keygraphy.data_path", return_value=path),
                patch("keygraphy.curses.wrapper") as wrapper,
                patch("sys.argv", ["keygraphy.py", "--key-cost", "ü=2"]),
            ):
                self.assertEqual(main(), 0)
                self.assertEqual(wrapper.call_args.args[1].key_cost("ü"), 2)
            self.assertEqual(load_progress(path).key_cost("ü"), 2)
            with (
                patch("keygraphy.data_path", return_value=path),
                patch("keygraphy.curses.wrapper") as wrapper,
                patch("sys.argv", ["keygraphy.py"]),
            ):
                self.assertEqual(main(), 0)
                self.assertEqual(wrapper.call_args.args[1].key_cost("ü"), 2)

    def test_result_explains_normalized_time_and_total_for_composed_focus(self):
        progress = Progress()
        session = Session(progress, "aü")
        session.focus = "ü"
        session.add("a", now=1)
        session.add("ü", now=1.6)
        session.commit()
        window = Mock()
        window.getmaxyx.return_value = (18, 60)
        with patch("keygraphy.safe_addstr") as output, patch("keygraphy.attr", return_value=0):
            draw_result(window, session, progress, [], False, 1000)
        texts = [call.args[3] for call in output.call_args_list]
        self.assertIn("ms/pulsación · 600 ms total / 3", texts)
        self.assertTrue(any("200 ms" in text for text in texts))


class BookTests(unittest.TestCase):
    def test_bundled_books_have_twenty_four_cantos(self):
        for slug in ("la-iliada", "la-odisea"):
            book = load_book(slug)
            self.assertEqual(len(book.sections), 24)
            self.assertTrue(all(section.chunks for section in book.sections))
            self.assertTrue(
                all(
                    300 <= len(chunk) <= 500
                    for section in book.sections
                    for chunk in section.chunks
                )
            )
            self.assertTrue(
                all(
                    "LATIN" in unicodedata.name(character, "")
                    for section in book.sections
                    for chunk in section.chunks
                    for character in chunk
                    if character.isalpha()
                )
            )

    def test_first_book_level_requires_only_lowercase_words_and_spaces(self):
        text = "¡Cántame, pingüino y niño!"
        expected = "".join(
            character for _, character in book_expected_positions(text, 0)
        )
        self.assertEqual(expected, "cantame pinguino y niño")

    def test_second_book_level_adds_tildes_before_punctuation(self):
        text = "¡Cántame, pingüino!"
        expected = "".join(
            character for _, character in book_expected_positions(text, 1)
        )
        self.assertEqual(expected, "cántame pingüino")

    def test_book_text_is_not_filtered_by_practice_letters(self):
        progress = Progress(selected_book="la-odisea")
        book = load_book(progress.selected_book)
        _, text = current_book_chunk(progress, book)
        session = BookSession(text, progress.book_level)
        self.assertEqual(session.text, book.sections[0].chunks[0])
        self.assertGreater(set(text.lower()) - set(progress.active_keys + " "), set())
        self.assertIn("háblame, musa", text.lower())

    def test_book_levels_add_punctuation_cumulatively(self):
        text = "Hola, mundo. ¿Sí?"
        comma = "".join(
            character for _, character in book_expected_positions(text, 2)
        )
        period = "".join(
            character for _, character in book_expected_positions(text, 3)
        )
        questions = "".join(
            character for _, character in book_expected_positions(text, 6)
        )
        complete = "".join(
            character
            for _, character in book_expected_positions(text, len(BOOK_LEVELS) - 1)
        )
        self.assertEqual(comma, "hola, mundo sí")
        self.assertEqual(period, "hola, mundo. sí")
        self.assertEqual(questions, "hola, mundo. ¿sí?")
        self.assertEqual(complete, text)

    def test_paragraphs_remain_word_boundaries_and_enter_at_full_level(self):
        text = "Fin.\n\nPrincipio"
        words = "".join(
            character for _, character in book_expected_positions(text, 0)
        )
        complete = "".join(
            character
            for _, character in book_expected_positions(text, len(BOOK_LEVELS) - 1)
        )
        self.assertEqual(words, "fin principio")
        self.assertEqual(complete, "Fin.\nPrincipio")

        session = BookSession(text, len(BOOK_LEVELS) - 1)
        for character in complete:
            session.add(character, now=1.0)
        self.assertTrue(session.complete)

    def test_book_session_tracks_errors_without_touching_letter_progress(self):
        progress = Progress()
        session = BookSession("Hola.", 0)
        for character in "hoxa":
            session.add(character, now=1.0)
        self.assertFalse(session.complete)
        self.assertEqual(session.attempts, 4)
        self.assertEqual(session.error_positions, {2})
        session.add("l", now=1.0)
        session.add("a", now=1.0)
        self.assertTrue(session.complete)
        self.assertEqual(progress.letters, {})

    def test_book_level_advances_after_accurate_practice(self):
        progress = Progress(
            book_level_attempts=BOOK_LEVEL_MIN_ATTEMPTS - 4,
            book_level_correct=BOOK_LEVEL_MIN_ATTEMPTS - 4,
        )
        session = BookSession("hola", 0)
        for character in "hola":
            session.add(character, now=1.0)
        self.assertEqual(record_book_session(progress, session), "tildes")
        self.assertEqual(progress.book_level, 1)
        self.assertEqual(progress.book_level_attempts, 0)

    def test_book_position_moves_between_sections_and_completes(self):
        book = Book(
            "test",
            "Test",
            (
                BookSection("Uno", ("a",)),
                BookSection("Dos", ("b",)),
            ),
        )
        progress = Progress(selected_book="la-iliada")
        progress.books[book.slug] = BookPosition()
        self.assertFalse(advance_book_position(progress, book))
        self.assertEqual(progress.books[book.slug], BookPosition(section=1))
        self.assertFalse(progress.books[book.slug].completed)
        self.assertTrue(advance_book_position(progress, book))
        self.assertTrue(progress.books[book.slug].completed)

    def test_current_chunk_repairs_out_of_range_saved_position(self):
        book = Book("test", "Test", (BookSection("Uno", ("texto",)),))
        progress = Progress()
        progress.books[book.slug] = BookPosition(section=99, chunk=99)
        position, chunk = current_book_chunk(progress, book)
        self.assertEqual((position.section, position.chunk, chunk), (0, 0, "texto"))

    def test_current_chunk_resets_position_after_content_revision(self):
        book = Book("test", "Test", (BookSection("Uno", ("texto",)),), "new")
        progress = Progress()
        progress.books[book.slug] = BookPosition(0, 0, True, "old")
        position, _ = current_book_chunk(progress, book)
        self.assertEqual(position, BookPosition(revision="new"))

    def test_book_wrapping_preserves_every_character_except_newlines(self):
        text = "uno dos tres\n\ncuatro cinco"
        pieces = [text[start:end] for start, end in wrap_book_ranges(text, 8)]
        self.assertEqual("".join(pieces), text.replace("\n", ""))

    def test_book_view_shows_only_two_lines_around_current_position(self):
        text = "uno dos tres cuatro cinco seis siete ocho nueve diez"
        ranges = visible_book_ranges(text, 10, text.index("siete"))
        self.assertEqual(len(ranges), 2)
        self.assertTrue(any(start <= text.index("siete") < end for start, end in ranges))

    def test_book_line_width_fits_the_minimum_terminal(self):
        self.assertEqual(book_text_width(42), 34)
        self.assertEqual(book_text_width(100), BOOK_LINE_WIDTH)

    def test_book_exercise_extends_past_two_lines_to_end_a_sentence(self):
        text = (
            "uno dos tres cuatro cinco seis siete ocho nueve diez once doce. "
            "segunda oración que debe quedar para el ejercicio siguiente."
        )
        exercise, next_offset = book_exercise(text, 0, 10)
        self.assertGreaterEqual(len(wrap_book_ranges(exercise, 10)), 2)
        self.assertTrue(exercise.endswith("."))
        self.assertLess(next_offset, len(text))

    def test_consecutive_book_exercises_preserve_the_complete_text(self):
        text = "uno dos tres cuatro cinco seis siete ocho nueve diez once doce"
        pieces = []
        offset = 0
        while offset < len(text):
            exercise, offset = book_exercise(text, offset, 10)
            pieces.append(exercise)
        self.assertEqual(" ".join(pieces), text)

    def test_book_exercise_omits_trailing_space_before_enter(self):
        text = (
            "uno dos tres cuatro cinco seis siete ocho. "
            "nueve diez once doce trece catorce."
        )
        exercise, next_offset = book_exercise(text, 0, 10)
        expected = book_expected_positions(exercise, 0)
        self.assertFalse(exercise.endswith(" "))
        self.assertNotEqual(expected[-1][1], " ")
        self.assertGreater(next_offset, len(exercise))

    def test_book_exercise_boundaries_are_cached(self):
        text = " ".join(["palabra"] * 100)
        book_exercise_boundaries.cache_clear()
        first = book_exercise_boundaries(text, BOOK_LINE_WIDTH)
        second = book_exercise_boundaries(text, BOOK_LINE_WIDTH)
        self.assertIs(first, second)
        self.assertEqual(book_exercise_boundaries.cache_info().hits, 1)

    def test_book_exercise_continues_across_storage_chunks(self):
        book = Book(
            "test",
            "Test",
            (
                BookSection(
                    "Uno",
                    (
                        "uno dos tres cuatro cinco.",
                        "seis siete ocho nueve diez. once doce trece catorce.",
                    ),
                ),
            ),
        )
        progress = Progress()
        position, exercise, next_offset, current, total = current_book_exercise(
            progress, book, 12
        )
        self.assertEqual(position.section, 0)
        self.assertIn("tres cuatro", exercise)
        self.assertGreaterEqual(len(wrap_book_ranges(exercise, 12)), 2)
        self.assertTrue(exercise.endswith("."))
        self.assertEqual(current, 1)
        self.assertGreater(total, 1)

        advance_book_position(progress, book, next_offset)
        _, _, _, next_current, next_total = current_book_exercise(progress, book, 12)
        self.assertEqual(next_current, 2)
        self.assertEqual(next_total, total)

    def test_legacy_offset_aligns_to_a_complete_two_line_exercise(self):
        sentence = " ".join(["palabra"] * 12) + "."
        text = f"{sentence} {sentence} {sentence}"
        book = Book("test", "Test", (BookSection("Uno", (text,)),))
        progress = Progress(books={"test": BookPosition(offset=17)})
        position, exercise, _, _, _ = current_book_exercise(
            progress, book, BOOK_LINE_WIDTH
        )
        self.assertIn(position.offset, (0, *book_exercise_boundaries(text, BOOK_LINE_WIDTH)))
        self.assertGreaterEqual(len(wrap_book_ranges(exercise, BOOK_LINE_WIDTH)), 2)
        self.assertTrue(exercise.endswith("."))

    def test_section_text_preserves_chunk_order(self):
        section = BookSection("Uno", ("primero", "segundo", "tercero"))
        self.assertEqual(book_section_text(section), "primero segundo tercero")


class ModeSwitchTests(unittest.TestCase):
    def test_keyboard_layout_renders_compact_layout(self):
        progress = Progress()
        window = Mock()
        window.getmaxyx.return_value = (10, 80)

        with patch("keygraphy.safe_addstr") as addstr, patch(
            "keygraphy.attr", return_value=0
        ) as style:
            draw_keyboard_layout(window, progress, "ú", 1)

        rendered = [call.args[3] for call in addstr.call_args_list]
        styles = [call.args[0] for call in style.call_args_list]
        self.assertEqual(KEYBOARD_ROWS[0], tuple("qwertyuiop´¨"))
        self.assertEqual(KEYBOARD_ROWS[1], tuple("asdfghjklñ"))
        self.assertEqual(KEYBOARD_ROWS[2], tuple("zxcvbnm,.-"))
        self.assertEqual(
            {KEYBOARD_FINGER_BY_KEY[key] for key in "qazpñ-´"},
            {0},
        )
        self.assertEqual(
            {KEYBOARD_FINGER_BY_KEY[key] for key in "wsxol."},
            {1},
        )
        self.assertEqual(
            {KEYBOARD_FINGER_BY_KEY[key] for key in "edcik,"},
            {2},
        )
        self.assertEqual(
            {KEYBOARD_FINGER_BY_KEY[key] for key in "rfvtgbyhnujm"},
            {3},
        )
        self.assertTrue(
            all(
                Theme.KEYBOARD_FINGER_THEMES[finger] in styles
                for finger in range(4)
            )
        )
        self.assertTrue(
            all(
                Theme.KEYBOARD_LOCKED_THEMES[finger] in styles
                for finger in range(4)
            )
        )
        self.assertIn(" q ", rendered)
        q_positions = [
            (call.args[1], call.args[2])
            for call in addstr.call_args_list
            if call.args[3] == " q "
        ]
        w_positions = [
            (call.args[1], call.args[2])
            for call in addstr.call_args_list
            if call.args[3] == " w "
        ]
        t_positions = [
            (call.args[1], call.args[2])
            for call in addstr.call_args_list
            if call.args[3] == " t "
        ]
        y_positions = [
            (call.args[1], call.args[2])
            for call in addstr.call_args_list
            if call.args[3] == " y "
        ]
        z_positions = [
            (call.args[1], call.args[2])
            for call in addstr.call_args_list
            if call.args[3] == " z "
        ]
        a_positions = [
            (call.args[1], call.args[2])
            for call in addstr.call_args_list
            if call.args[3] == " a "
        ]
        self.assertEqual(len(q_positions), 1)
        self.assertEqual(w_positions[0][1] - q_positions[0][1], 3)
        self.assertEqual(y_positions[0][1] - t_positions[0][1], 5)
        self.assertEqual(a_positions[0][1] - q_positions[0][1], 1)
        self.assertEqual(z_positions[0][1] - q_positions[0][1], 2)
        self.assertIn("[u]", rendered)
        self.assertIn("[´]", rendered)
        self.assertIn(" ñ ", rendered)
        self.assertIn(" - ", rendered)
        self.assertIn(" , ", rendered)
        self.assertIn(" . ", rendered)
        self.assertNotIn("SPACE", rendered)

    def test_options_selects_keyboard_view(self):
        progress = Progress()
        window = Mock()
        window.getmaxyx.return_value = (24, 80)
        window.get_wch.side_effect = ["j", "j", "j", "h", "\n"]

        with (
            patch("keygraphy.safe_addstr"),
            patch("keygraphy.attr", return_value=0),
        ):
            result = choose_options(window, progress)

        self.assertEqual(
            result,
            (
                progress.mode,
                progress.word_package,
                progress.selected_book,
                progress.target_wpm,
                "letters",
            ),
        )

    def test_space_on_keyboard_option_changes_only_view(self):
        progress = Progress()
        window = Mock()
        window.getmaxyx.return_value = (24, 80)
        window.get_wch.side_effect = ["j", "j", "j", " ", "\n"]

        with (
            patch("keygraphy.safe_addstr"),
            patch("keygraphy.attr", return_value=0),
        ):
            result = choose_options(window, progress)

        self.assertEqual(result[1], progress.word_package)
        self.assertEqual(result[4], "letters")

    def test_escape_cancels_keyboard_view_change(self):
        progress = Progress()
        window = Mock()
        window.getmaxyx.return_value = (24, 80)
        window.get_wch.side_effect = ["j", "j", "j", "h", "\x1b"]

        with (
            patch("keygraphy.safe_addstr"),
            patch("keygraphy.attr", return_value=0),
        ):
            result = choose_options(window, progress)

        self.assertEqual(result[4], "keyboard")

    def test_practice_footer_uses_keyboard_view_when_selected(self):
        progress = Progress(keyboard_view="keyboard")
        session = Session(progress, "casa")
        window = Mock()
        window.getmaxyx.return_value = (24, 80)

        with (
            patch("keygraphy.safe_addstr") as addstr,
            patch("keygraphy.attr", return_value=0),
            patch("keygraphy.draw_keyboard_layout") as keyboard,
        ):
            draw(window, session)

        keyboard.assert_called_once_with(window, progress, session.focus, 20)
        rendered = [call.args[3] for call in addstr.call_args_list]
        self.assertFalse(any("ppm" in text for text in rendered))
        self.assertFalse(any("─" in text for text in rendered))
        self.assertFalse(any("Esc opciones" in text for text in rendered))

    def test_practice_shows_shift_hint_and_uppercase_focus_key(self):
        progress = Progress()
        master_keys(progress, LETTER_ORDER)
        session = Session(
            progress,
            generate_lesson(progress, random.Random(3), target_length=80),
        )
        self.assertEqual(session.focus, "E")
        window = Mock()
        window.getmaxyx.return_value = (24, 80)

        with (
            patch("keygraphy.safe_addstr") as addstr,
            patch("keygraphy.attr", return_value=0),
        ):
            draw(window, session)

        rendered = [call.args[3] for call in addstr.call_args_list]
        self.assertIn("⇧ Mayús", rendered)
        self.assertTrue(any("[E]" in text for text in rendered))

    def test_keyboard_marks_accented_capital_focus(self):
        progress = Progress()
        window = Mock()
        window.getmaxyx.return_value = (10, 80)

        with patch("keygraphy.safe_addstr") as addstr, patch(
            "keygraphy.attr", return_value=0
        ):
            draw_keyboard_layout(window, progress, "Ó", 1)

        rendered = [call.args[3] for call in addstr.call_args_list]
        self.assertIn("[Ó]", rendered)
        self.assertIn("[´]", rendered)

    def test_practice_letter_bar_hides_performance_metrics(self):
        progress = Progress(keyboard_view="letters")
        session = Session(progress, "casa")
        window = Mock()
        window.getmaxyx.return_value = (24, 80)

        with (
            patch("keygraphy.safe_addstr") as addstr,
            patch("keygraphy.attr", return_value=0),
        ):
            draw(window, session)

        rendered = [call.args[3] for call in addstr.call_args_list]
        self.assertTrue(any("─" in text for text in rendered))
        self.assertFalse(any("ppm" in text for text in rendered))
        self.assertFalse(any("%" in text for text in rendered))
        self.assertFalse(any("Esc opciones" in text for text in rendered))

    def test_apply_options_persists_keyboard_view_change(self):
        progress = Progress()
        window = Mock()
        with (
            patch(
                "keygraphy.choose_options",
                return_value=(
                    progress.mode,
                    progress.word_package,
                    progress.selected_book,
                    progress.target_wpm,
                    "letters",
                ),
            ),
            patch("keygraphy.save_progress") as save,
        ):
            changed = apply_options(window, progress)

        self.assertTrue(changed)
        self.assertEqual(progress.keyboard_view, "letters")
        save.assert_called_once_with(progress)

    def test_book_view_shows_statistics_at_the_bottom_without_options_hint(self):
        progress = Progress(mode="book", book_level=1)
        progress.book_level_attempts = 325
        progress.book_level_correct = 312
        book = Book("test", "Test", (BookSection("Uno", ("hola",)),))
        session = BookSession("hola", progress.book_level)
        window = Mock()
        window.getmaxyx.return_value = (24, 80)

        with patch("keygraphy.safe_addstr") as addstr, patch(
            "keygraphy.attr", return_value=0
        ):
            draw_book(window, progress, book, session)

        rendered = [call.args[1:] for call in addstr.call_args_list]
        self.assertIn(
            (23, 3, "Nivel: tildes · 325/500 pulsaciones · 96%/95%", 0),
            rendered,
        )
        self.assertFalse(any("Esc opciones" in args[2] for args in rendered))

    def test_target_speed_changes_in_five_wpm_steps_and_stays_in_range(self):
        self.assertEqual(change_target_wpm(35, 1), 40)
        self.assertEqual(change_target_wpm(35, -1), 30)
        self.assertEqual(change_target_wpm(150, 1), 150)
        self.assertEqual(change_target_wpm(15, -1), 15)

    def test_source_cycles_word_packages_in_practice_mode(self):
        mode, words, book = cycle_option(
            "practice", "es-la", "la-iliada", "source", 1
        )
        self.assertEqual((mode, words, book), ("practice", "en-us", "la-iliada"))

    def test_source_cycles_books_in_book_mode(self):
        mode, words, book = cycle_option(
            "book", "es-la", "la-iliada", "source", 1
        )
        self.assertEqual((mode, words, book), ("book", "es-la", "la-odisea"))

    def test_mode_change_preserves_each_modes_source(self):
        mode, words, book = cycle_option(
            "practice", "en-us", "la-odisea", "mode", 1
        )
        self.assertEqual((mode, words, book), ("book", "en-us", "la-odisea"))

    def test_book_and_practice_use_the_same_vertical_centering(self):
        self.assertEqual(centered_text_y(24, 2), 11)

    def test_run_starts_book_session_immediately_after_mode_change(self):
        progress = Progress(mode="practice")

        def switch_mode(_window, current):
            current.mode = "book"
            return "switch"

        window = Mock()
        with (
            patch("keygraphy.curses.curs_set"),
            patch("keygraphy.Theme.initialize"),
            patch("keygraphy.run_practice_session", side_effect=switch_mode),
            patch("keygraphy.run_book_session", return_value="exit") as book_session,
        ):
            run(window, progress)
        book_session.assert_called_once_with(window, progress)

    def test_escape_opens_options_without_resetting_the_practice_session(self):
        progress = Progress()
        window = Mock()
        window.get_wch.side_effect = ["\x1b"]

        with (
            patch("keygraphy.generate_lesson", return_value="a"),
            patch("keygraphy.draw"),
            patch("keygraphy.apply_options", return_value=False) as options,
            patch("keygraphy.save_progress"),
        ):
            result = run_practice_session(window, progress)

        self.assertEqual(result, "switch")
        options.assert_called_once_with(window, progress)

    def test_escape_resets_active_session_even_when_options_are_cancelled(self):
        progress = Progress()
        window = Mock()
        window.get_wch.side_effect = ["a", "\x1b"]

        with (
            patch("keygraphy.generate_lesson", return_value="aa"),
            patch("keygraphy.draw"),
            patch("keygraphy.apply_options", return_value=False),
        ):
            result = run_practice_session(window, progress)

        self.assertEqual(result, "switch")
        self.assertEqual(progress.letters, {})

    def test_book_session_stops_at_sentence_end_until_enter(self):
        sentence = " ".join(["palabra"] * 25) + "."
        text = f"{sentence} {sentence} {sentence}"
        book = Book("test", "Test", (BookSection("Uno", (text,)),))
        progress = Progress(mode="book")
        exercise, next_offset = book_exercise(text, 0, BOOK_LINE_WIDTH)
        typed = "".join(character for _, character in book_expected_positions(exercise, 0))
        window = Mock()
        window.getmaxyx.return_value = (24, 20)
        window.get_wch.side_effect = [*typed, "\n"]

        with (
            patch("keygraphy.load_book", return_value=book),
            patch("keygraphy.draw_book") as draw_book,
            patch("keygraphy.save_progress"),
        ):
            result = run_book_session(window, progress)

        self.assertEqual(result, "next")
        self.assertEqual(progress.book_position(book.slug).offset, next_offset)
        self.assertFalse(progress.book_position(book.slug).completed)
        self.assertGreaterEqual(draw_book.call_count, len(typed) + 1)
        self.assertEqual(len(draw_book.call_args.args), 4)


class ResultTests(unittest.TestCase):
    def test_celebration_gauge_only_for_unlock_or_record_and_sits_behind_scores(self):
        progress = Progress()
        session = Session(progress, "casa")
        for height, width in ((10, 42), (18, 60), (24, 80)):
            for unlocked, record in (([], False), (["t"], False), ([], True), (["t"], True)):
                with self.subTest(size=(height, width), unlocked=unlocked, record=record):
                    window = self._window()
                    window.getmaxyx.return_value = (height, width)
                    with patch("keygraphy.safe_addstr") as output, patch("keygraphy.attr", return_value=0):
                        draw_result(window, session, progress, unlocked, record, 0)
                    calls = [call.args for call in output.call_args_list]
                    gauge_calls = [
                        call
                        for call in calls
                        if any("\u2801" <= c <= "\u28ff" for c in call[3])
                    ]
                    self.assertEqual(bool(gauge_calls), bool(unlocked or record))
                    if unlocked or record:
                        self.assertEqual(
                            len(gauge_calls), min(height - 2, (width - 1) // 2)
                        )
                        score_top = next(call for call in calls if call[3].startswith("┌"))
                        gauge_left = min(call[2] for call in gauge_calls)
                        gauge_right = max(call[2] + len(call[3]) for call in gauge_calls)
                        gauge_top = min(call[1] for call in gauge_calls)
                        gauge_bottom = max(call[1] + 1 for call in gauge_calls)
                        gauge_width = max(len(call[3]) for call in gauge_calls)
                        gauge_center = gauge_left + gauge_width / 2
                        scores_left = score_top[2]
                        scores_right = scores_left + len(score_top[3])
                        self.assertAlmostEqual(gauge_center / width, 0.75, delta=0.05)
                        self.assertGreater(gauge_right, scores_left)
                        self.assertLess(gauge_left, scores_right)
                        self.assertLess(gauge_top, score_top[1] + 4)
                        self.assertGreater(gauge_bottom, score_top[1])
                    for _, y, x, text, *_ in calls:
                        self.assertTrue(0 <= y < height)
                        self.assertTrue(0 <= x and x + len(text) < width)
                        self.assertNotIn("\x1b", text)
                    self.assertTrue(any("CURRENT" in call[3] for call in calls))

    def test_gauge_accelerates_then_holds_redline(self):
        from keygraphy import result_gauge_rows, result_gauge_value

        self.assertEqual(result_gauge_value(0), 0)
        self.assertGreater(result_gauge_value(0.4), result_gauge_value(0.1))
        values = [result_gauge_value(t / 100) for t in range(100, 1000)]
        self.assertTrue(all(0.94 < value < 0.98 for value in values))
        self.assertGreater(max(values) - min(values), 0.01)
        self.assertNotEqual(result_gauge_rows(8, 0), result_gauge_rows(8, 1))

    def test_completed_keys_record_still_celebrates(self):
        progress = Progress()
        master_keys(progress)
        session = Session(progress, "casa")
        session.focus = "ü"
        with patch("keygraphy.safe_addstr") as output, patch("keygraphy.attr", return_value=0):
            draw_result(self._window(), session, progress, [], True, 0)
        text = "".join(call.args[3] for call in output.call_args_list)
        self.assertIn("NEW RECORD", text)
        self.assertIn("ppm", text)
        self.assertNotIn("[ü]", text)
        self.assertTrue(any("\u2801" <= c <= "\u28ff" for c in text))

    def test_result_titles_mark_phase_transitions(self):
        progress = Progress()
        master_keys(progress, LETTER_ORDER)
        session = Session(progress, "casa")
        session.focus = "ü"
        with patch("keygraphy.safe_addstr") as output, patch(
            "keygraphy.attr", return_value=0
        ):
            draw_result(self._window(), session, progress, ["E"], False, 0)
        text = "".join(call.args[3] for call in output.call_args_list)
        self.assertIn("MAYÚSCULAS DESBLOQUEADAS", text)

        progress.letters["E"] = LetterStat(time_ms=200, best_time_ms=200)
        session = Session(progress, "casa")
        session.focus = "E"
        with patch("keygraphy.safe_addstr") as output, patch(
            "keygraphy.attr", return_value=0
        ):
            draw_result(self._window(), session, progress, ["A"], False, 0)
        text = "".join(call.args[3] for call in output.call_args_list)
        self.assertIn("MAYÚSCULA NUEVA", text)

    def test_result_titles_mark_sign_transitions(self):
        progress = Progress()
        master_keys(progress, KEY_ORDER[:-2])
        session = Session(progress, "casa")
        session.focus = KEY_ORDER[-3]
        self.assertTrue(session.focus.isupper())
        with patch("keygraphy.safe_addstr") as output, patch(
            "keygraphy.attr", return_value=0
        ):
            draw_result(self._window(), session, progress, ["."], False, 0)
        text = "".join(call.args[3] for call in output.call_args_list)
        self.assertIn("SIGNOS DESBLOQUEADOS", text)
        self.assertIn(f"[{KEY_ORDER[-3]}]", text)

        progress.letters["."] = LetterStat(time_ms=200, best_time_ms=200)
        session = Session(progress, "casa")
        session.focus = "."
        with patch("keygraphy.safe_addstr") as output, patch(
            "keygraphy.attr", return_value=0
        ):
            draw_result(self._window(), session, progress, [","], False, 0)
        text = "".join(call.args[3] for call in output.call_args_list)
        self.assertIn("SIGNO NUEVO", text)

        progress.letters[","] = LetterStat(time_ms=200, best_time_ms=200)
        session = Session(progress, "casa")
        session.focus = ","
        with patch("keygraphy.safe_addstr") as output, patch(
            "keygraphy.attr", return_value=0
        ):
            draw_result(self._window(), session, progress, [], False, 0)
        text = "".join(call.args[3] for call in output.call_args_list)
        self.assertIn("DOMINIO COMPLETO", text)

    def _window(self):
        window = Mock()
        window.getmaxyx.return_value = (24, 80)
        window.erase = Mock()
        window.refresh = Mock()
        window.addnstr = Mock()
        return window

    def _render(self, session, progress, unlocked, hi_score, ticks):
        with patch("keygraphy.curses.has_colors", return_value=False):
            draw_result(
                self._window(),
                session,
                progress,
                unlocked,
                hi_score,
                ticks,
            )

    def test_result_screen_renders_letter_box_and_message(self):
        progress = Progress()
        session = Session(progress, "casa")
        session.focus = "s"
        progress.stat("s").time_ms = 400
        progress.stat("s").best_time_ms = 320
        self._render(session, progress, [], False, 10)

    def test_result_screen_counts_current_time_from_zero(self):
        progress = Progress()
        session = Session(progress, "casa")
        session.focus = "s"
        progress.stat("s").time_ms = 400
        progress.stat("s").best_time_ms = 320
        window = self._window()

        with patch("keygraphy.safe_addstr") as addstr, patch(
            "keygraphy.attr", return_value=0
        ):
            draw_result(window, session, progress, [], False, 0)
            first_frame = [call.args[3] for call in addstr.call_args_list]
            addstr.reset_mock()
            draw_result(window, session, progress, [], False, 50)
            final_frame = [call.args[3] for call in addstr.call_args_list]

        self.assertTrue(any(text.count("000 ms") == 3 for text in first_frame))
        self.assertTrue(any("400 ms" in text for text in final_frame))
        self.assertTrue(any("320 ms" in text for text in final_frame))
        self.assertTrue(any("343 ms" in text for text in final_frame))

    def test_result_screen_blinks_when_target_is_reached(self):
        progress = Progress()
        session = Session(progress, "casa")
        session.focus = "a"
        progress.stat("a").time_ms = 300
        progress.stat("a").best_time_ms = 300
        self._render(session, progress, [], False, 0)
        self._render(session, progress, [], False, 8)
        self._render(session, progress, [], False, 16)

    def test_result_screen_shows_high_score_only_when_best_is_broken(self):
        progress = Progress()
        session = Session(progress, "casa")
        session.focus = "s"
        progress.stat("s").time_ms = 400
        progress.stat("s").best_time_ms = 300
        self._render(session, progress, [], True, 10)

    def test_result_screen_handles_empty_focus(self):
        progress = Progress()
        master_keys(progress)
        session = Session(progress, "casa")
        session.focus = None
        self._render(session, progress, [], False, 10)

    def test_result_screen_shows_wpm_after_completing_keys(self):
        progress = Progress()
        master_keys(progress)
        progress.best_wpm_by_package[progress.word_package] = 45
        session = Session(progress, "casa")
        session.typed = list(session.text)
        session.started_at = 1.0
        session.finished_at = 2.0
        window = self._window()

        with patch("keygraphy.safe_addstr") as addstr, patch(
            "keygraphy.attr", return_value=0
        ):
            draw_result(window, session, progress, [], False, 100)

        rendered = [call.args[3] for call in addstr.call_args_list]
        self.assertTrue(any("ppm" in text for text in rendered))
        self.assertTrue(any("45" in text for text in rendered))

    def test_escape_restores_blocking_input_before_opening_options(self):
        progress = Progress()
        session = Session(progress, "casa")
        window = self._window()
        window.get_wch.return_value = "\x1b"

        def assert_blocking_input(*_args):
            self.assertEqual(window.timeout.call_args, unittest.mock.call(-1))

        with (
            patch("keygraphy.draw_result"),
            patch("keygraphy.apply_options", side_effect=assert_blocking_input),
        ):
            self.assertEqual(run_result(window, session, progress, [], False), "next")

        self.assertEqual(
            window.timeout.call_args_list,
            [unittest.mock.call(16), unittest.mock.call(-1), unittest.mock.call(-1)],
        )


class PersistenceTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            progress = Progress(word_package="es-la", keyboard_view="letters")
            progress.stat("e").append_lesson(1, 0, 220)
            progress.best_wpm_by_package["es-la"] = 42
            progress.post_alphabet_focus = "e"
            progress.post_alphabet_focus_sessions = 2
            save_progress(progress, path)
            loaded = load_progress(path)
            self.assertEqual(loaded.stat("e").hits, 1)
            self.assertEqual(loaded.stat("e").time_ms, 220)
            self.assertEqual(loaded.stat("e").best_time_ms, 220)
            self.assertEqual(loaded.word_package, "es-la")
            self.assertEqual(loaded.keyboard_view, "letters")
            self.assertEqual(loaded.best_wpm, 42)
            self.assertEqual(loaded.post_alphabet_focus, "e")
            self.assertEqual(loaded.post_alphabet_focus_sessions, 2)
            json.loads(path.read_text(encoding="utf-8"))

    def test_alphabet_complete_save_enters_capitals_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            progress = Progress()
            master_keys(progress, LETTER_ORDER)
            progress.post_alphabet_focus = "f"
            progress.post_alphabet_focus_sessions = 3
            save_progress(progress, path)

            loaded = load_progress(path)
            self.assertFalse(loaded.keys_complete)
            self.assertEqual(loaded.active_keys, LETTER_ORDER + "E")
            self.assertEqual(loaded.lesson_focus(), "E")

    def test_post_complete_focus_can_be_a_sign(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            progress = Progress()
            master_keys(progress)
            progress.post_alphabet_focus = "."
            save_progress(progress, path)

            loaded = load_progress(path)
            self.assertTrue(loaded.keys_complete)
            self.assertEqual(loaded.post_alphabet_focus, ".")
            self.assertEqual(loaded.lesson_focus(), ".")

    def test_legacy_save_without_keyboard_view_keeps_letters_bar(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text('{"word_package": "es-la"}', encoding="utf-8")
            self.assertEqual(load_progress(path).keyboard_view, "letters")

    def test_invalid_saved_word_package_uses_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text('{"word_package": "missing"}', encoding="utf-8")
            self.assertEqual(load_progress(path).word_package, "es-la")

    def test_malformed_letter_does_not_discard_other_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(
                '{"mode": "book", "letters": {'
                '"e": {"hits": null, "time_ms": "bad"}, '
                '"a": {"hits": 4, "misses": 1, "time_ms": 200}}}',
                encoding="utf-8",
            )
            loaded = load_progress(path)
            self.assertEqual(loaded.mode, "book")
            self.assertNotIn("e", loaded.letters)
            self.assertEqual(loaded.stat("a").hits, 4)

    def test_legacy_current_time_becomes_initial_best_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(
                '{"unlocked": 15, "letters": {'
                '"b": {"hits": 20, "misses": 2, "time_ms": 240}}}',
                encoding="utf-8",
            )
            loaded = load_progress(path)
            self.assertEqual(loaded.stat("b").time_ms, 240)
            self.assertEqual(loaded.stat("b").best_time_ms, 240)

    def test_legacy_mastered_letter_does_not_regress_during_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(
                '{"unlocked": 15, "target_wpm": 35, "letters": {'
                '"p": {"hits": 20, "misses": 2, "time_ms": 500}}}',
                encoding="utf-8",
            )
            loaded = load_progress(path)
            self.assertEqual(loaded.stat("p").time_ms, 500)
            self.assertAlmostEqual(loaded.stat("p").best_time_ms, 60000 / 175)

    def test_round_trip_preserves_book_mode_and_position(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            progress = Progress(
                mode="book",
                selected_book="la-odisea",
                book_level=3,
                book_level_attempts=120,
                book_level_correct=116,
                books={"la-odisea": BookPosition(2, 0, False, "revision", 345)},
            )
            save_progress(progress, path)
            loaded = load_progress(path)
            self.assertEqual(loaded.mode, "book")
            self.assertEqual(loaded.selected_book, "la-odisea")
            self.assertEqual(loaded.book_level, 3)
            self.assertEqual(loaded.book_level_attempts, 120)
            self.assertEqual(loaded.book_level_correct, 116)
            self.assertEqual(
                loaded.books["la-odisea"],
                BookPosition(2, 0, False, "revision", 345),
            )

    def test_malformed_books_do_not_discard_adaptive_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(
                '{"unlocked": 9, "books": [], "letters": {"e": {"hits": 4}}}',
                encoding="utf-8",
            )
            loaded = load_progress(path)
            self.assertEqual(loaded.stat("e").hits, 4)
            self.assertEqual(loaded.books, {})

    def test_non_boolean_completed_value_is_not_truthy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(
                '{"books": {"la-iliada": {"completed": "false"}}}',
                encoding="utf-8",
            )
            loaded = load_progress(path)
            self.assertFalse(loaded.books["la-iliada"].completed)

    def test_malformed_book_level_does_not_discard_adaptive_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(
                '{"unlocked": 9, "book_level": "bad", '
                '"book_level_attempts": [], "book_level_correct": {}}',
                encoding="utf-8",
            )
            loaded = load_progress(path)
            self.assertEqual(loaded.book_level, 0)
            self.assertEqual(loaded.book_level_attempts, 0)
            self.assertEqual(loaded.book_level_correct, 0)


if __name__ == "__main__":
    unittest.main()
