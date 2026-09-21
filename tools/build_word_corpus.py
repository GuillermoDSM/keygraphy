#!/usr/bin/env python3
"""Build the Spanish practice corpus from the bundled public-domain books."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOK_PATHS = (
    ROOT / "data" / "books" / "la-iliada.json",
    ROOT / "data" / "books" / "la-odisea.json",
)
OUTPUT = ROOT / "data" / "words-es-literatura.json"
METADATA = ROOT / "data" / "words-es-literatura.meta.json"
WORD_LIMIT = 10_000
PRACTICE_ALPHABET = set("abcdefghijklmnopqrstuvwxyzñáéíóú")
TOKEN = re.compile(r"[a-záéíóúüñ]+", re.IGNORECASE)


def book_words(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    words: list[str] = []
    for section in payload["sections"]:
        for chunk in section["chunks"]:
            for match in TOKEN.finditer(chunk):
                word = match.group().lower()
                if len(word) > 1 and set(word) <= PRACTICE_ALPHABET:
                    words.append(word)
    return words


def main() -> int:
    counts: Counter[str] = Counter()
    letter_counts: Counter[str] = Counter()
    source_metadata: list[dict[str, str | int]] = []
    for path in BOOK_PATHS:
        words = book_words(path)
        counts.update(words)
        letter_counts.update("".join(words))
        source_metadata.append(
            {
                "path": str(path.relative_to(ROOT)),
                "word_tokens": len(words),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    ranked = sorted(counts, key=lambda word: (-counts[word], word))[:WORD_LIMIT]
    if len(ranked) < 5_000:
        raise RuntimeError(f"El corpus solo contiene {len(ranked)} palabras únicas")
    letter_order = "".join(
        sorted(letter_counts, key=lambda letter: (-letter_counts[letter], letter))
    )

    OUTPUT.write_text(
        json.dumps(ranked, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    metadata = {
        "word_count": len(ranked),
        "unique_source_words": len(counts),
        "source_tokens": sum(counts.values()),
        "letter_order": letter_order,
        "sources": source_metadata,
        "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
    }
    METADATA.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {len(ranked)} words from {sum(counts.values())} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
