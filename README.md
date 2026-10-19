# keygraphy

Minimal adaptive typing practice for Linux terminals. Keygraphy focuses lessons
on the least confident key and adds a new one after every active key has
reached the target speed.

By default, lessons use a 9,943-word `es-LA` corpus ranked from contemporary
multi-source language data. An `en-US` package is also available. Words are
filtered to the currently unlocked letters. If fewer than 15 contain the focus
letter, the remaining slots are filled with generated pseudowords.

Timing uses milliseconds per required key press. Keygraphy averages
the total character production time over each completed lesson, smooths it with
a 0.1 factor, and divides it by the character's key cost. Progress uses the best
smoothed speed ever reached, so a mastered letter does not unexpectedly replace
the current focus. Accuracy is still recorded and displayed, but it does not
block progression. After every lesson, a compact summary shows the current and
best timing for the focus.

## Phases

The curriculum advances in three phases, one key at a time:

1. Letters. Six lowercase letters start; new ones arrive in frequency order
   until the alphabet is complete.
2. Capitals. The same order again, each trained at the start of words; about
   half the words begin with the focus capital. Only capitals that begin at
   least one corpus word are included, and practice draws on the 40 most common
   ones so lessons stay natural.
3. Punctuation. The period, then the comma, and finally the apostrophe in the
   `en-US` package only, using a curated list of real contractions (`don't`,
   `it's`, `I'm`...). Marks attach to word ends, a period capitalizes the next
   word, and previously mastered marks keep appearing for review.

Once every key is mastered, the result screen switches to current and best PPM,
and each lesson reviews the slowest key, held for three lessons.

Each language uses its own frequency order. The `es-LA` package is ranked from
nine modern Spanish open books balanced across literature, history, and business
and economics. The sources are pan-Hispanic rather than limited to one country;
see [`CORPUS.md`](CORPUS.md) for the methodology and attribution. The `en-US`
package remains a separate general English list. The terminal handles the
physical keyboard mapping.

Select the English package directly with:

```sh
python3 keygraphy.py --words en-us
```

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
offers the `es-LA` and `en-US` word packages and an adjustable 15-150 WPM target,
while book
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

## Timing and key costs

The initial keyboard assumption uses two presses for `áéíóú` (dead accent key
plus vowel), three for `ü` (Shift plus dead diaeresis key plus vowel), and one
for ordinary lowercase letters, including `ñ`. Uppercase letters add one press
for Shift: `A` costs two, `Á` three, and `Ü` four. This estimate assumes a
separate Shift press for each uppercase character.

For example, 600 ms to produce `ü` counts as 200 ms per press for the speed
target and letter progression. Keygraphy keeps both the total and normalized
current/best timings in the local statistics. The result screen labels letter
timings as `ms/pulsación` and shows the total and divisor for multi-key letters.
Exercise WPM still uses text characters and actual elapsed time.

The terminal delivers composed characters rather than individual Shift and
dead-key events. Configure costs for your physical keyboard independently of
the word package, using repeatable overrides:

```sh
python3 keygraphy.py --key-cost 'ü=2' --key-cost 'Ü=3'
```

Each override accepts one printable character and an integer from 1 to 10.
Keygraphy saves these overrides, recalculates existing normalized timings from
their totals, and uses them on future runs. A lowercase override also changes
its uppercase cost unless you set an explicit uppercase override.
Keygraphy converts older statistics once when loading them. Corrected errors
count toward accuracy but do not contribute speed samples; the first character
starts the timer and has no timing sample.

## Pixel gallery

The isolated speed-animation gallery is an idea board for choosing a future
visual direction without changing the main application:

```sh
python3 pixel_gallery.py
python3 pixel_gallery.py --snapshot --plain --example 1
```

Use `n`/`p` to change examples, `g` to open the numbered catalog, `m` to
change palettes, `Space` to pause, `r` to reseed particles, and `q` or
`Escape` to exit. The renderer falls back to a static plain-text snapshot when
it cannot use terminal controls.

## Test

```sh
python3 -m unittest -v
```

## Word lists

The Spanish list is generated from the nine sources in
`data/words-es-la.sources.json`. The generated entries retain their score, rank,
coverage, and per-source counts; the application loads only the `word` field.
Rebuild it with Python 3.10 or newer and `pdftotext`:

```sh
python3 tools/build_word_corpus.py
```

The Spanish sources use CC BY 4.0 and require attribution. The bundled `en-US`
list is retained from `wordfreq` 3.1.1 and remains subject to its CC BY-SA 4.0
notice: <https://github.com/rspeer/wordfreq/blob/master/NOTICE.md>.

## Bundled books

`data/books/` contains Spanish editions of Homer's *La Ilíada* and *La Odisea*,
translated by Luis Segalá y Estalella and sourced from Project Gutenberg. To
download the UTF-8 sources and rebuild the canto-based typing content, run:

```sh
python3 tools/build_book_library.py
```

Project Gutenberg's terms and trademark rules apply to those source texts:
<https://www.gutenberg.org/policy/license.html>.
