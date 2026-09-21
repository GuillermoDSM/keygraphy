# keygraphy

Minimal adaptive typing practice for Linux terminals. Keygraphy focuses lessons
on the least confident letter and adds a new one after every active letter has
reached the target speed.

By default, lessons use a 10,000-word Spanish corpus ranked from the bundled
classical texts. Words are filtered to the currently unlocked letters. If fewer
than 15 contain the focus letter, the remaining slots are filled with generated
pseudowords.

Per-letter speed is averaged over each completed lesson and smoothed with a
0.1 factor. Progress uses the best smoothed speed ever reached, so a mastered
letter does not unexpectedly replace the current focus. Accuracy is still
recorded and displayed, but it does not block letter progression. After every
lesson, a compact summary shows the current and best timing for the focus.

Spanish lessons use the frequency order computed from the bundled corpus. Spain
and Latin American keyboard layouts use the same language model; the terminal
handles the physical keyboard mapping.

## Run

Requires Python 3.10 or newer and a terminal with curses support.

```sh
python3 keygraphy.py
```

Correct characters appear green. A mistake does not advance and leaves that
character red and underlined after it is corrected. The current character is
cyan and underlined, and future text is dimmed. Press `Backspace` to restart and
discard the current attempt, or `Ctrl+C` to exit. Progress is saved automatically
to:

```text
~/.local/share/keygraphy/stats.json
```

Press `Esc` to open options. Choose a mode and its source: adaptive practice
offers the bundled word corpus and an adjustable 15-150 WPM target, while book
transcription offers bundled books. Use the up/down arrows to choose a setting,
left/right to change it (in 5 WPM steps for the target), `Enter` to apply, and
`Esc` to cancel. In practice,
`Ver teclado` selects either the letter bar or the compact color-coded keyboard
shown below the lesson. New installations use the keyboard by default; the
selection is saved with progress.
Selections and book positions are restored on the next run.
`Ctrl+S` is intentionally not used because many Unix terminals reserve it for
software flow control (XOFF).

Book mode starts with lowercase words without accent marks while preserving the
complete original passage on screen, two lines at a time. Accents are introduced
next; as accuracy improves, punctuation groups are added one at a time until the
edition is transcribed exactly. Book statistics are independent from adaptive
letter progress. Each exercise fills at least two lines, continues to the end of
the current sentence, and then waits for `Enter`. The interface keeps two lines
visible at a time while longer sentences scroll in reading order, and the
fragment counter advances in the header.

Reset all progress with:

```sh
python3 keygraphy.py --reset
```

## Test

```sh
python3 -m unittest -v
```

## Bundled books

`data/books/` contains Spanish editions of Homer's *La Ilíada* and *La Odisea*,
translated by Luis Segalá y Estalella and sourced from Project Gutenberg. To
download the UTF-8 sources and rebuild the canto-based typing content, run:

```sh
python3 tools/build_book_library.py
```

See `ATTRIBUTION.md` for source and public-domain details. To rebuild the word
corpus after changing the bundled books, run:

```sh
python3 tools/build_word_corpus.py
```
