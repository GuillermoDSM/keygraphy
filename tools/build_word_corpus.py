#!/usr/bin/env python3
"""Build the bundled Spanish practice corpus from licensed open books."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import unicodedata
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MANIFEST = DATA_DIR / "words-es-la.sources.json"
OUTPUT = DATA_DIR / "words-es-la.json"
METADATA = DATA_DIR / "words-es-la.meta.json"
WORD_COUNT = 10_000
MIN_SOURCE_COVERAGE = 2
MAX_HTML_PAGES = 120
USER_AGENT = "keygraphy-corpus-builder/1.0"
ALPHABET = set("abcdefghijklmnñopqrstuvwxyzáéíóúü")
ALPHABET_ORDER = "abcdefghijklmnñopqrstuvwxyzáéíóúü"
TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# Filter recurring English boilerplate and PDF extraction fragments.
EXCLUDED_TOKENS = frozenset({"under", "licensed", "vol", "ción", "df"})
IGNORED_HTML_TAGS = {
    "aside",
    "button",
    "canvas",
    "footer",
    "form",
    "header",
    "nav",
    "noscript",
    "script",
    "style",
    "svg",
}
GENRES = ("literatura", "historia", "negocios")


class HTMLDocumentParser(HTMLParser):
    """Collect readable book text and links without third-party dependencies."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._content_depth = 0
        self._has_content = False
        self._content: list[str] = []
        self._fallback: list[str] = []
        self._all_links: list[str] = []
        self._content_links: list[str] = []
        self._fallback_links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._all_links.append(href)
        if tag in IGNORED_HTML_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag in {"article", "main"}:
            self._content_depth += 1
            self._has_content = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                links = self._content_links if self._content_depth else self._fallback_links
                links.append(href)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag in {"article", "main"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in IGNORED_HTML_TAGS:
            self._ignored_depth = max(self._ignored_depth - 1, 0)
            return
        if self._ignored_depth:
            return
        if tag in {"article", "main"}:
            self._content_depth = max(self._content_depth - 1, 0)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or not data.strip():
            return
        self._fallback.append(data)
        if self._content_depth:
            self._content.append(data)

    @property
    def text(self) -> str:
        chunks = self._content if self._has_content and self._content else self._fallback
        return "\n".join(chunks)

    @property
    def links(self) -> list[str]:
        return self._all_links


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "es,en;q=0.5",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_url(url: str, base: str) -> str:
    resolved = urllib.parse.urljoin(base, url)
    parts = urllib.parse.urlsplit(resolved)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def in_scope(url: str, spec: dict[str, object]) -> bool:
    source = urllib.parse.urlsplit(str(spec["source_url"]))
    candidate = urllib.parse.urlsplit(url)
    prefix = urllib.parse.unquote(str(spec.get("crawl_prefix", source.path)))
    candidate_path = urllib.parse.unquote(candidate.path)
    if not prefix.endswith("/"):
        prefix += "/"
    if candidate.scheme not in {"http", "https"} or candidate.netloc != source.netloc:
        return False
    if not candidate_path.startswith(prefix):
        return False
    relative_path = candidate_path[len(prefix):].strip("/")
    max_depth = int(spec.get("crawl_depth", 99))
    if relative_path and relative_path.count("/") + 1 > max_depth:
        return False
    if any(candidate_path.lower().endswith(extension) for extension in (".pdf", ".epub", ".zip")):
        return False
    if any(
        marker in candidate_path
        for marker in ("/wp-admin/", "/wp-json/", "/wp-login", "/open/")
    ):
        return False
    if any(
        marker in candidate_path.lower()
        for marker in ("/feed", "/comments", "/tag/", "/category/", "/search")
    ):
        return False
    if candidate.query and "download" in candidate.query.lower():
        return False
    return True


def extract_html(spec: dict[str, object]) -> tuple[str, list[dict[str, str]]]:
    start_url = str(spec["source_url"])
    pending = [start_url]
    visited: set[str] = set()
    pages: list[dict[str, str]] = []
    max_pages = int(spec.get("max_pages", MAX_HTML_PAGES))

    while pending and len(visited) < max_pages:
        url = pending.pop(0)
        if url in visited or not in_scope(url, spec) and url != start_url:
            continue
        visited.add(url)
        try:
            raw = download(url)
        except (HTTPError, URLError) as error:
            raise RuntimeError(f"No se pudo descargar {url}: {error}") from error
        parser = HTMLDocumentParser()
        parser.feed(raw.decode("utf-8", errors="replace"))
        pages.append({"url": url, "sha256": sha256(raw), "text": parser.text})
        links = sorted(
            {
                normalize_url(link, url)
                for link in parser.links
                if in_scope(normalize_url(link, url), spec)
            }
        )
        pending.extend(link for link in links if link not in visited and link not in pending)

    if not pages:
        raise RuntimeError(f"No se pudo extraer contenido HTML de {start_url}")
    if pending:
        raise RuntimeError(
            f"El libro {spec['id']} supera el límite de {max_pages} páginas"
        )
    return "\n".join(page["text"] for page in pages), pages


def extract_pdf(raw: bytes, url: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as source:
        source.write(raw)
        source.flush()
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", source.name, "-"],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "Los libros PDF requieren el comando pdftotext instalado"
            ) from error
        except subprocess.CalledProcessError as error:
            details = error.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"No se pudo extraer {url}: {details}") from error
    return result.stdout.decode("utf-8", errors="replace")


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\xa0", " ")
    text = URL_RE.sub(" ", text)
    text = re.sub(r"\[[0-9]+\]", " ", text)
    return text


def is_sentence_start(text: str, position: int) -> bool:
    previous = text[:position].rstrip()
    return not previous or previous[-1] in ".!?¿¡\n"


def tokens_from_text(text: str) -> Counter[str]:
    text = clean_text(text)
    counts: Counter[str] = Counter()
    for match in TOKEN_RE.finditer(text):
        raw = match.group(0)
        word = unicodedata.normalize("NFC", raw.casefold())
        if len(word) < 2 or not set(word) <= ALPHABET:
            continue
        if word in EXCLUDED_TOKENS:
            continue
        # Keep sentence-initial common words while dropping likely proper names.
        if raw[0].isupper() and not is_sentence_start(text, match.start()):
            continue
        if any(character.isupper() for character in raw[1:]):
            continue
        counts[word] += 1
    return counts


def validate_manifest(manifest: dict[str, object]) -> list[dict[str, object]]:
    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != 9:
        raise ValueError("El manifiesto debe contener exactamente nueve fuentes")
    if manifest.get("locale") != "es-la":
        raise ValueError("El manifiesto debe ser para la locale es-la")
    minimum_year = int(manifest.get("minimum_year", 1970))
    by_genre: Counter[str] = Counter()
    validated: list[dict[str, object]] = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("Cada fuente del manifiesto debe ser un objeto")
        required = {
            "id",
            "title",
            "author",
            "year",
            "genre",
            "language",
            "license",
            "license_url",
            "record_url",
            "source_url",
            "source_format",
        }
        missing = required - source.keys()
        if missing:
            raise ValueError(f"Faltan campos en {source.get('id', '<sin id>')}: {missing}")
        if source["language"] != "es" or int(source["year"]) < minimum_year:
            raise ValueError(f"Fuente fuera de los criterios: {source['id']}")
        if source["genre"] not in GENRES:
            raise ValueError(f"Género no admitido en {source['id']}: {source['genre']}")
        if "CC BY" not in str(source["license"]) and "CC0" not in str(source["license"]):
            raise ValueError(f"Licencia no admitida en {source['id']}: {source['license']}")
        if any(marker in str(source["license"]).upper() for marker in ("NC", "ND", "SA")):
            raise ValueError(f"Licencia no comercial o derivada en {source['id']}")
        by_genre[str(source["genre"])] += 1
        validated.append(source)
    if tuple(sorted(by_genre)) != tuple(sorted(GENRES)) or any(
        by_genre[genre] != 3 for genre in GENRES
    ):
        raise ValueError(f"Se requieren tres fuentes por género: {by_genre}")
    return validated


def load_sources(manifest_path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("El manifiesto debe ser un objeto JSON")
    return manifest, validate_manifest(manifest)


def extract_source(spec: dict[str, object]) -> tuple[Counter[str], dict[str, object]]:
    raw = download(str(spec["source_url"]))
    source_hash = sha256(raw)
    expected_hash = spec.get("source_sha256")
    if expected_hash and source_hash != expected_hash:
        raise RuntimeError(
            f"Cambió el hash de {spec['id']}: se esperaba {expected_hash}, se obtuvo {source_hash}"
        )
    if spec["source_format"] == "pdf":
        text = extract_pdf(raw, str(spec["source_url"]))
        pages = []
    elif spec["source_format"] == "html":
        text, pages = extract_html(spec)
    else:
        raise ValueError(f"Formato no admitido en {spec['id']}: {spec['source_format']}")
    counts = tokens_from_text(text)
    token_count = sum(counts.values())
    if token_count < 1000:
        raise RuntimeError(
            f"El texto extraído de {spec['id']} solo contiene {token_count} tokens válidos"
        )
    record = {
        **spec,
        "source_sha256": source_hash,
        "text_sha256": hashlib.sha256(clean_text(text).encode("utf-8")).hexdigest(),
        "page_count": len(pages) or None,
        "page_hashes": [{"url": page["url"], "sha256": page["sha256"]} for page in pages],
        "token_count": token_count,
        "unique_word_count": len(counts),
    }
    return counts, record


def frequency(count: int, token_count: int) -> float:
    return count / token_count * 1_000_000


def score_words(
    sources: list[dict[str, object]],
    counts_by_source: dict[str, Counter[str]],
    token_counts: dict[str, int],
) -> list[dict[str, object]]:
    genre_sources: dict[str, list[dict[str, object]]] = defaultdict(list)
    for source in sources:
        genre_sources[str(source["genre"])].append(source)
    candidates = set().union(*(counts.keys() for counts in counts_by_source.values()))
    ranked: list[tuple[str, float, int, dict[str, int]]] = []
    for word in candidates:
        counts = {
            str(source["id"]): counts_by_source[str(source["id"])].get(word, 0)
            for source in sources
        }
        coverage = sum(count > 0 for count in counts.values())
        if coverage < MIN_SOURCE_COVERAGE:
            continue
        genre_scores = []
        for genre in GENRES:
            genre_scores.append(
                mean(
                    frequency(
                        counts[str(source["id"])], token_counts[str(source["id"])]
                    )
                    for source in genre_sources[genre]
                )
            )
        ranked.append((word, mean(genre_scores), coverage, counts))
    ranked.sort(key=lambda item: (-item[1], -item[2], item[0]))
    if len(ranked) < WORD_COUNT:
        raise RuntimeError(
            f"Solo se obtuvieron {len(ranked)} palabras con cobertura mínima; "
            f"se necesitan {WORD_COUNT}"
        )
    return [
        {
            "word": word,
            "score": round(score, 6),
            "rank": rank,
            "coverage": coverage,
            "counts": counts,
        }
        for rank, (word, score, coverage, counts) in enumerate(
            ranked[:WORD_COUNT], start=1
        )
    ]


def letter_order(
    sources: list[dict[str, object]],
    counts_by_source: dict[str, Counter[str]],
) -> str:
    genre_scores: dict[str, dict[str, float]] = {}
    for genre in GENRES:
        genre_sources = [source for source in sources if source["genre"] == genre]
        source_scores: list[dict[str, float]] = []
        for source in genre_sources:
            counts = counts_by_source[str(source["id"])]
            total = sum(count * len(word) for word, count in counts.items())
            source_scores.append(
                {
                    letter: sum(
                        count * word.count(letter)
                        for word, count in counts.items()
                    )
                    / total
                    if total
                    else 0.0
                    for letter in ALPHABET_ORDER
                }
            )
        genre_scores[genre] = {
            letter: mean(scores[letter] for scores in source_scores)
            for letter in ALPHABET_ORDER
        }
    balanced = {
        letter: mean(genre_scores[genre][letter] for genre in GENRES)
        for letter in ALPHABET_ORDER
    }
    return "".join(sorted(ALPHABET_ORDER, key=lambda letter: (-balanced[letter], letter)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--metadata", type=Path, default=METADATA)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest, sources = load_sources(args.manifest)
    counts_by_source: dict[str, Counter[str]] = {}
    source_records: list[dict[str, object]] = []
    for source in sources:
        counts, record = extract_source(source)
        source_id = str(source["id"])
        counts_by_source[source_id] = counts
        source_records.append(record)
        print(
            f"{source_id}: {record['token_count']} tokens, "
            f"{record['unique_word_count']} palabras únicas"
        )

    token_counts = {
        str(record["id"]): int(record["token_count"]) for record in source_records
    }
    entries = score_words(sources, counts_by_source, token_counts)
    output_bytes = (json.dumps(entries, ensure_ascii=False, indent=1) + "\n").encode(
        "utf-8"
    )
    args.output.write_bytes(output_bytes)
    metadata = {
        "locale": manifest["locale"],
        "source": "nine modern Spanish open books",
        "minimum_year": manifest["minimum_year"],
        "license_policy": manifest["license_policy"],
        "genres": {genre: 3 for genre in GENRES},
        "word_count": len(entries),
        "candidate_count": len(
            set().union(*(counts.keys() for counts in counts_by_source.values()))
        ),
        "minimum_source_coverage": MIN_SOURCE_COVERAGE,
        "scoring": {
            "per_source": "count / valid_token_count * 1,000,000",
            "genre_score": "mean of the three source frequencies",
            "score": "mean of the three genre scores",
            "tie_breakers": ["source coverage descending", "word ascending"],
        },
        "letter_order": letter_order(sources, counts_by_source),
        "sources": source_records,
        "sha256": sha256(output_bytes),
    }
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{args.output.relative_to(ROOT)}: generated {len(entries)} words")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
