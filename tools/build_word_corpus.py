#!/usr/bin/env python3
"""Build locale-specific practice corpora from wordfreq."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from wordfreq import top_n_list


ROOT = Path(__file__).resolve().parents[1]
WORD_COUNT = 10_000
CANDIDATE_COUNT = 50_000
WORDLIST = "large"
WORDFREQ_VERSION = "3.1.1"
WORDFREQ_URL = "https://github.com/rspeer/wordfreq"
DATA_LICENSE = "CC BY-SA 4.0"
LANGUAGES = {
    "es-la": {
        "source_language": "es",
        "alphabet": set("abcdefghijklmnñopqrstuvwxyzáéíóúü"),
        "output": ROOT / "data" / "words-es-la.json",
        "metadata": ROOT / "data" / "words-es-la.meta.json",
    },
    "en-us": {
        "source_language": "en",
        "alphabet": set("abcdefghijklmnopqrstuvwxyz"),
        "output": ROOT / "data" / "words-en-us.json",
        "metadata": ROOT / "data" / "words-en-us.meta.json",
    },
}


def build_words(language: str, alphabet: set[str]) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()
    for raw in top_n_list(language, CANDIDATE_COUNT, wordlist=WORDLIST):
        word = raw.casefold()
        if len(word) < 2 or not word.isalpha() or not set(word) <= alphabet:
            continue
        if word in seen:
            continue
        seen.add(word)
        words.append(word)
        if len(words) == WORD_COUNT:
            break
    if len(words) != WORD_COUNT:
        raise RuntimeError(
            f"{language}: wordfreq solo produjo {len(words)} palabras utilizables"
        )
    return words


def main() -> int:
    for locale, config in LANGUAGES.items():
        words = build_words(config["source_language"], config["alphabet"])
        letter_counts: Counter[str] = Counter("".join(words))
        letter_order = "".join(
            sorted(
                config["alphabet"],
                key=lambda letter: (-letter_counts[letter], letter),
            )
        )
        output = config["output"]
        output.write_text(
            json.dumps(words, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        metadata = {
            "locale": locale,
            "source_language": config["source_language"],
            "source": "wordfreq",
            "wordfreq_version": WORDFREQ_VERSION,
            "wordlist": WORDLIST,
            "snapshot": "language usage through 2021",
            "word_count": len(words),
            "letter_order": letter_order,
            "source_url": WORDFREQ_URL,
            "data_license": DATA_LICENSE,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }
        config["metadata"].write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{locale}: generated {len(words)} words")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
