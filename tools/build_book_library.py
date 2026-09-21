#!/usr/bin/env python3
"""Download and build the bundled Project Gutenberg typing books."""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "books"
MIN_CHUNK = 300
TARGET_CHUNK = 400
MAX_CHUNK = 500
BOOKS = (
    {
        "slug": "la-iliada",
        "title": "La Ilíada",
        "gutenberg_id": 57654,
        "source_url": "https://www.gutenberg.org/cache/epub/57654/pg57654.txt",
        "source_sha256": "67e4402b72927b4cdbc73d710a641c2b0293b594e26b8083323e7193932b3efd",
    },
    {
        "slug": "la-odisea",
        "title": "La Odisea",
        "gutenberg_id": 58221,
        "source_url": "https://www.gutenberg.org/cache/epub/58221/pg58221.txt",
        "source_sha256": "5a07183328d9ff6fc4b9d49fc9c7b15f9b793a8add1ef001908694de8341acce",
    },
)
ROMAN = (
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI",
    "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
    "XXI", "XXII", "XXIII", "XXIV",
)
CANTO = re.compile(r"^CANTO (PRIMERO|[IVXLCDM]+)\s*$", re.MULTILINE)
ILLUSTRATION = re.compile(r"\[Ilustración.*?\]", re.IGNORECASE | re.DOTALL)
NATURAL_BREAK = re.compile(r"[.!?…][»”]?(?=\s)|\n\n")
CLAUSE_BREAK = re.compile(r"[,;:](?=\s)")
WORD_BREAK = re.compile(r"(?=\s)")


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "keygraphy-book-builder/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def strip_gutenberg_wrapper(source: str) -> str:
    start = re.search(
        r"^\*\*\* START OF THE PROJECT GUTENBERG EBOOK .+? \*\*\*\s*$",
        source,
        re.MULTILINE,
    )
    end = re.search(
        r"^\*\*\* END OF THE PROJECT GUTENBERG EBOOK .+? \*\*\*\s*$",
        source,
        re.MULTILINE,
    )
    if not start or not end or start.end() >= end.start():
        raise ValueError("Project Gutenberg start/end markers were not found")
    return source[start.end():end.start()]


def clean_body(raw: str) -> str:
    raw = ILLUSTRATION.sub("", raw).replace("_", "")
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", raw):
        paragraph = re.sub(r"\s+", " ", block).strip()
        if not paragraph:
            continue
        if re.match(r"^\[\d+\]\s", paragraph):
            continue
        paragraph = re.sub(r"\[\d+\]", "", paragraph)
        paragraph = re.sub(r"^\d+\s+", "", paragraph)
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def choose_break(text: str, lower: int, target: int, stop: int) -> int:
    for pattern in (NATURAL_BREAK, CLAUSE_BREAK, WORD_BREAK):
        candidates = [
            match.end()
            for match in pattern.finditer(text, lower, stop + 1)
            if lower <= match.end() <= stop
        ]
        if candidates:
            return min(candidates, key=lambda position: (abs(position - target), -position))
    return stop


def chunks_for(body: str) -> list[str]:
    chunks: list[str] = []
    chunk_count = round(len(body) / TARGET_CHUNK)
    chunk_count = max(chunk_count, math.ceil(len(body) / MAX_CHUNK), 1)
    chunk_count = min(chunk_count, max(len(body) // MIN_CHUNK, 1))
    start = 0
    while chunk_count > 1:
        remaining = len(body) - start
        target = start + round(remaining / chunk_count)
        # Allow for up to two paragraph-separator characters removed by strip().
        padded_minimum = MIN_CHUNK + 2
        lower = max(
            start + padded_minimum,
            len(body) - MAX_CHUNK * (chunk_count - 1),
        )
        stop = min(
            start + MAX_CHUNK,
            len(body) - padded_minimum * (chunk_count - 1),
        )
        end = choose_break(body, lower, target, stop)
        chunks.append(body[start:end].strip())
        start = end
        while start < len(body) and body[start].isspace():
            start += 1
        chunk_count -= 1
    chunks.append(body[start:].strip())
    return chunks


def extract_sections(source: str) -> list[dict[str, object]]:
    book = strip_gutenberg_wrapper(source)
    first_canto = CANTO.search(book)
    if not first_canto:
        raise ValueError("First canto was not found")
    finish = re.search(r"^FIN\s*$", book[first_canto.start():], re.MULTILINE)
    if not finish:
        raise ValueError("End of poem marker was not found")
    poem = book[first_canto.start():first_canto.start() + finish.start()]
    matches = list(CANTO.finditer(poem))
    if len(matches) != 24:
        raise ValueError(f"Expected 24 cantos, found {len(matches)}")

    sections: list[dict[str, object]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(poem)
        segment = poem[match.end():end].strip()
        subtitle_match = re.match(r"([^\n]+)", segment)
        if not subtitle_match:
            raise ValueError(f"Canto {index + 1} has no subtitle")
        subtitle = subtitle_match.group(1).strip()
        body = clean_body(segment[subtitle_match.end():])
        if not body:
            raise ValueError(f"Canto {index + 1} has no body")
        sections.append(
            {
                "title": f"Canto {ROMAN[index]}: {subtitle}",
                "chunks": chunks_for(body),
            }
        )
    return sections


def build_book(spec: dict[str, object], source_bytes: bytes) -> dict[str, object]:
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != spec["source_sha256"]:
        raise ValueError(
            f"Source hash changed for Project Gutenberg {spec['gutenberg_id']}: "
            f"{source_sha256}"
        )
    source = source_bytes.decode("utf-8-sig").replace("\r\n", "\n")
    sections = extract_sections(source)
    encoded_sections = json.dumps(
        sections,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "metadata": {
            "title": spec["title"],
            "author": "Homero",
            "translator": "Luis Segalá y Estalella",
            "language": "es",
            "gutenberg_id": spec["gutenberg_id"],
            "ebook_url": f"https://www.gutenberg.org/ebooks/{spec['gutenberg_id']}",
            "source_url": spec["source_url"],
            "source_sha256": source_sha256,
            "content_revision": hashlib.sha256(encoded_sections).hexdigest()[:16],
            "public_domain_status": "Public domain in the United States",
        },
        "sections": sections,
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for spec in BOOKS:
        source_bytes = download(str(spec["source_url"]))
        book = build_book(spec, source_bytes)
        output = OUTPUT_DIR / f"{spec['slug']}.json"
        output.write_text(
            json.dumps(book, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        chunks = sum(len(section["chunks"]) for section in book["sections"])
        characters = sum(
            len(chunk)
            for section in book["sections"]
            for chunk in section["chunks"]
        )
        print(
            f"{output.relative_to(ROOT)}: {len(book['sections'])} sections, "
            f"{chunks} chunks, {characters} characters"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
