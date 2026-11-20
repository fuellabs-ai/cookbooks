#!/usr/bin/env python3
"""Show me where it says that.

Check a question against a folder of your own documents before you answer
it. Two cut-offs give three verdicts: at or above the upper cut-off the
section is returned with its file and heading ("Found"); below the lower
cut-off the verdict is "Not in these documents", the 3 nearest sections are
labelled "closest, but not an answer", and the question goes to a gaps list;
in between the verdict is "Check this", which shows the top section and says
a person should confirm it.

Embeddings only. No LLM writes an answer.

The model is HobbyLM-Embed 140M loaded through Sentence Transformers with
trust_remote_code=True. Documents are embedded with prompt_name="passage"
and questions with prompt_name="query". The model adds the prefixes itself,
so the text you pass in must not contain "passage: " or "query: ".

Usage:
    python show_me.py docs/ "can I get a refund after 30 days?"
    python show_me.py docs/ --questions questions.csv --out-dir out

The two cut-offs are settings. calibrate.py recommends a pair from your own
labelled questions and saves both to cutoff.json in the docs folder. A fixed
cut-off does not carry over between models or document sets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

DEFAULT_MODEL = "harims95/hobbylm-embed-140m"
DEFAULT_CUTOFF_UPPER = 0.75
DEFAULT_CUTOFF_LOWER = 0.65
DEFAULT_MAX_WORDS = 220
DEFAULT_TOP_K = 3
SUPPORTED_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".html",
    ".htm",
    ".pdf",
    ".docx",
}
CONFIG_NAME = "cutoff.json"
GAPS_NAME = "gaps.md"
CHECK_NAME = "check_this.md"
EXCERPT_CHARS = 260
VERDICT_FOUND = "Found"
VERDICT_CHECK = "Check this"
VERDICT_NOT_FOUND = "Not in these documents"
RESULTS_COLUMNS = ["question", "verdict", "top_section", "score"]
OUTPUT_FILENAMES = {"gaps.md", "check_this.md", "cutoff.json"}


@dataclass
class Section:
    heading: str
    text: str


@dataclass
class Chunk:
    file: str
    heading: str
    text: str
    ordinal: int

    @property
    def label(self) -> str:
        if self.heading:
            return f"{self.file} > {self.heading}"
        return self.file

    @property
    def embedding_text(self) -> str:
        # The body is embedded. File name and heading stay as metadata for
        # the result, and are not mixed into the passage vector.
        return self.text


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _flush_sections(
    sections: list[Section], heading_parts: Sequence[str], body: list[str], fallback: str
) -> None:
    text = "\n".join(body).strip()
    if not text:
        return
    heading = " > ".join(part for part in heading_parts if part) or fallback
    sections.append(Section(heading=heading, text=text))


def _markdown_sections(text: str, fallback: str) -> list[Section]:
    sections: list[Section] = []
    heading_parts: list[str] = []
    body: list[str] = []

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            _flush_sections(sections, heading_parts, body, fallback)
            body = []
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_parts = heading_parts[: level - 1] + [title]
        else:
            body.append(line)

    _flush_sections(sections, heading_parts, body, fallback)
    if not sections and text.strip():
        sections.append(Section(heading=fallback, text=text.strip()))
    return sections


def _plain_sections(text: str, fallback: str) -> list[Section]:
    """Split plain text on setext and all-caps headings.

    Text without headings becomes one section. The chunker still splits it.
    """
    lines = text.splitlines()
    sections: list[Section] = []
    heading_parts: list[str] = []
    body: list[str] = []

    index = 0
    while index < len(lines):
        line = lines[index].strip()
        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
        is_setext = (
            bool(line)
            and len(line) <= 80
            and bool(re.fullmatch(r"=+|-+", next_line))
            and len(next_line) >= 3
        )
        is_caps = (
            bool(line)
            and len(line) <= 60
            and line.upper() == line
            and any(char.isalpha() for char in line)
        )

        if is_setext:
            _flush_sections(sections, heading_parts, body, fallback)
            body = []
            level = 1 if next_line.startswith("=") else 2
            heading_parts = heading_parts[: level - 1] + [line.title()]
            index += 2
            continue

        if is_caps:
            _flush_sections(sections, heading_parts, body, fallback)
            body = []
            heading_parts = [line.title()]
            index += 1
            continue

        body.append(lines[index])
        index += 1

    _flush_sections(sections, heading_parts, body, fallback)
    if not sections and text.strip():
        sections.append(Section(heading=fallback, text=text.strip()))
    return sections


class _HTMLToText(HTMLParser):
    BLOCK_TAGS = {
        "p",
        "div",
        "section",
        "article",
        "header",
        "footer",
        "main",
        "table",
        "ul",
        "ol",
        "tr",
        "br",
        "li",
    }
    SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            self.parts.append("\n\n" + "#" * level + " ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if re.fullmatch(r"h[1-6]", tag) or tag in self.BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_sections(text: str, fallback: str) -> list[Section]:
    parser = _HTMLToText()
    parser.feed(text)
    return _markdown_sections(parser.text(), fallback)


def _pdf_sections(path: Path, fallback: str) -> list[Section]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "Reading PDFs needs pypdf. Install it with: pip install pypdf"
        ) from exc

    reader = PdfReader(str(path))
    sections: list[Section] = []
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if page_text:
            sections.append(Section(heading=f"Page {page_number}", text=page_text))
    if not sections:
        sections.append(Section(heading=fallback, text=""))
    return sections


def _docx_sections(path: Path, fallback: str) -> list[Section]:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "Reading DOCX files needs python-docx. Install it with: "
            "pip install python-docx"
        ) from exc

    document = Document(str(path))
    sections: list[Section] = []
    heading_parts: list[str] = []
    body: list[str] = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = (paragraph.style.name or "").lower() if paragraph.style else ""
        heading_match = re.search(r"heading\s*(\d+)", style)
        if heading_match:
            _flush_sections(sections, heading_parts, body, fallback)
            body = []
            level = int(heading_match.group(1))
            heading_parts = heading_parts[: level - 1] + [text]
        elif style == "title":
            _flush_sections(sections, heading_parts, body, fallback)
            body = []
            heading_parts = [text]
        else:
            body.append(text)

    _flush_sections(sections, heading_parts, body, fallback)

    for table_number, table in enumerate(document.tables, start=1):
        rows: list[str] = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            sections.append(
                Section(heading=f"Table {table_number}", text="\n".join(rows))
            )

    if not sections:
        sections.append(Section(heading=fallback, text=""))
    return sections


def parse_file(path: Path, root: Path) -> list[Section]:
    """Parse one supported file into headed sections."""
    suffix = path.suffix.lower()
    fallback = path.stem
    raw = (
        path.read_text(encoding="utf-8", errors="replace")
        if suffix not in {".pdf", ".docx"}
        else ""
    )

    if suffix in {".md", ".markdown"}:
        return _markdown_sections(raw, fallback)
    if suffix in {".html", ".htm"}:
        return _html_sections(raw, fallback)
    if suffix == ".txt":
        return _plain_sections(raw, fallback)
    if suffix == ".pdf":
        return _pdf_sections(path, fallback)
    if suffix == ".docx":
        return _docx_sections(path, fallback)
    raise ValueError(f"Unsupported file type: {path}")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _split_long_unit(unit: str, max_words: int) -> list[str]:
    """Split one oversized paragraph into sentence or word sized pieces."""
    if len(unit.split()) <= max_words:
        return [unit]

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", unit) if part.strip()]
    pieces: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = sentence.split()
        if len(words) > max_words:
            if current:
                pieces.append(" ".join(current))
                current = []
                current_words = 0
            for start in range(0, len(words), max_words):
                pieces.append(" ".join(words[start : start + max_words]))
            continue
        if current and current_words + len(words) > max_words:
            pieces.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += len(words)

    if current:
        pieces.append(" ".join(current))
    return pieces


def chunk_sections(
    sections: Iterable[Section], file_label: str, max_words: int = DEFAULT_MAX_WORDS
) -> list[Chunk]:
    """Split sections into chunks well under the model's 1,024 token limit.

    A word is roughly 1.3 tokens in English, so the default 220 words is
    about 290 tokens. Each chunk keeps the file name and heading trail.
    """
    chunks: list[Chunk] = []
    ordinal = 0

    for section in sections:
        paragraphs = [
            " ".join(paragraph.split())
            for paragraph in re.split(r"\n\s*\n", section.text)
            if paragraph.strip()
        ]
        units: list[str] = []
        for paragraph in paragraphs:
            units.extend(_split_long_unit(paragraph, max_words))

        current: list[str] = []
        current_words = 0
        for unit in units:
            words = len(unit.split())
            if current and current_words + words > max_words:
                chunks.append(
                    Chunk(
                        file=file_label,
                        heading=section.heading,
                        text=" ".join(current),
                        ordinal=ordinal,
                    )
                )
                ordinal += 1
                current = []
                current_words = 0
            current.append(unit)
            current_words += words

        if current:
            chunks.append(
                Chunk(
                    file=file_label,
                    heading=section.heading,
                    text=" ".join(current),
                    ordinal=ordinal,
                )
            )
            ordinal += 1

    return chunks


def load_chunks(
    docs_folder: Path,
    max_words: int = DEFAULT_MAX_WORDS,
    cache_dir: Path | None = None,
) -> list[Chunk]:
    """Parse every supported file under docs_folder and return chunks."""
    docs_folder = Path(docs_folder).expanduser().resolve()
    if not docs_folder.is_dir():
        raise FileNotFoundError(f"Not a folder: {docs_folder}")

    chunks: list[Chunk] = []
    for path in sorted(docs_folder.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        relative = path.relative_to(docs_folder)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.name in OUTPUT_FILENAMES:
            # The gaps list, the Check this list and the cut-off config are
            # output, not documents to search.
            continue
        if cache_dir is not None:
            try:
                path.relative_to(Path(cache_dir).resolve())
                continue
            except ValueError:
                pass
        sections = parse_file(path, docs_folder)
        chunks.extend(chunk_sections(sections, str(relative), max_words=max_words))
    return chunks


# ---------------------------------------------------------------------------
# Embeddings and search
# ---------------------------------------------------------------------------


def load_model(model_name: str = DEFAULT_MODEL):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, trust_remote_code=True)


def _corpus_key(model_name: str, chunks: Sequence[Chunk]) -> str:
    digest = hashlib.sha256()
    digest.update(model_name.encode("utf-8"))
    digest.update(b"\0")
    for chunk in chunks:
        digest.update(chunk.embedding_text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:20]


def embed_chunks(
    chunks: Sequence[Chunk],
    model,
    model_name: str = DEFAULT_MODEL,
    cache_dir: Path | None = None,
    rebuild_cache: bool = False,
) -> np.ndarray:
    """Embed passages, reusing a cache keyed by the model and chunk text."""
    if not chunks:
        return np.zeros((0, 512), dtype=np.float32)

    cache_path = None
    if cache_dir is not None:
        cache_dir = Path(cache_dir).expanduser().resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{_corpus_key(model_name, chunks)}.npz"

    if cache_path is not None and cache_path.exists() and not rebuild_cache:
        saved = np.load(cache_path)
        vectors = saved["vectors"]
        if vectors.shape[0] == len(chunks):
            return np.asarray(vectors, dtype=np.float32)

    vectors = model.encode(
        [chunk.embedding_text for chunk in chunks],
        prompt_name="passage",
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    vectors = np.asarray(vectors, dtype=np.float32)

    if cache_path is not None:
        np.savez_compressed(cache_path, vectors=vectors)
    return vectors


def embed_queries(questions: Sequence[str], model) -> np.ndarray:
    if not questions:
        return np.zeros((0, 512), dtype=np.float32)
    vectors = model.encode(
        list(questions),
        prompt_name="query",
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return np.asarray(vectors, dtype=np.float32)


@dataclass
class DocumentIndex:
    docs_folder: Path
    chunks: list[Chunk]
    vectors: np.ndarray
    model: object
    model_name: str = DEFAULT_MODEL
    cutoff_upper: float = DEFAULT_CUTOFF_UPPER
    cutoff_lower: float = DEFAULT_CUTOFF_LOWER

    @classmethod
    def build(
        cls,
        docs_folder: str | Path,
        model=None,
        model_name: str = DEFAULT_MODEL,
        cache_dir: str | Path | None = None,
        rebuild_cache: bool = False,
        max_words: int = DEFAULT_MAX_WORDS,
        cutoff_upper: float | None = None,
        cutoff_lower: float | None = None,
    ) -> "DocumentIndex":
        docs_path = Path(docs_folder).expanduser().resolve()
        resolved_cache = (
            Path(cache_dir).expanduser().resolve()
            if cache_dir is not None
            else docs_path / ".hobbylm_cache"
        )
        chunks = load_chunks(docs_path, max_words=max_words, cache_dir=resolved_cache)
        if model is None:
            model = load_model(model_name)
        vectors = embed_chunks(
            chunks,
            model,
            model_name=model_name,
            cache_dir=resolved_cache,
            rebuild_cache=rebuild_cache,
        )
        if cutoff_upper is None or cutoff_lower is None:
            saved_upper, saved_lower = load_saved_cutoffs(docs_path)
            if cutoff_upper is None:
                cutoff_upper = saved_upper if saved_upper is not None else DEFAULT_CUTOFF_UPPER
            if cutoff_lower is None:
                cutoff_lower = saved_lower if saved_lower is not None else DEFAULT_CUTOFF_LOWER
        return cls(
            docs_folder=docs_path,
            chunks=chunks,
            vectors=vectors,
            model=model,
            model_name=model_name,
            cutoff_upper=cutoff_upper,
            cutoff_lower=cutoff_lower,
        )

    def score_all(self, questions: Sequence[str]) -> np.ndarray:
        """Score every question against every chunk. Rows sum to 1 per pair."""
        query_vectors = embed_queries(questions, self.model)
        return query_vectors @ self.vectors.T

    def search(
        self,
        question: str,
        cutoff_upper: float | None = None,
        cutoff_lower: float | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> dict:
        """Return the top chunks and a three-way verdict.

        At or above the upper cut-off: Found. Below the lower cut-off: Not
        in these documents. In between: Check this, because a person should
        confirm the section before anyone repeats it as an answer.
        """
        upper = self.cutoff_upper if cutoff_upper is None else cutoff_upper
        lower = self.cutoff_lower if cutoff_lower is None else cutoff_lower
        if not self.chunks:
            return {
                "question": question,
                "verdict": VERDICT_NOT_FOUND,
                "cutoff_upper": upper,
                "cutoff_lower": lower,
                "results": [],
                "message": "No supported documents were found in this folder.",
            }

        scores = self.score_all([question])[0]
        order = np.argsort(-scores)[: max(1, top_k)]

        results = []
        for position in order:
            chunk = self.chunks[int(position)]
            results.append(
                {
                    "file": chunk.file,
                    "heading": chunk.heading,
                    "label": chunk.label,
                    "score": float(scores[int(position)]),
                    "text": chunk.text,
                }
            )

        top_score = results[0]["score"] if results else 0.0
        if top_score >= upper:
            verdict = VERDICT_FOUND
        elif top_score >= lower:
            verdict = VERDICT_CHECK
        else:
            verdict = VERDICT_NOT_FOUND
        return {
            "question": question,
            "verdict": verdict,
            "cutoff_upper": upper,
            "cutoff_lower": lower,
            "results": results,
        }


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_saved_cutoffs(docs_folder: str | Path) -> tuple[float | None, float | None]:
    """Read the cut-offs that calibrate.py saved, if there are any.

    Older single-cut-off configs keep working: their "cutoff" value is used
    as the upper cut-off.
    """
    path = Path(docs_folder).expanduser().resolve() / CONFIG_NAME
    if not path.exists():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None

    def valid(value) -> float | None:
        if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0:
            return float(value)
        return None

    upper = valid(data.get("upper")) or valid(data.get("cutoff"))
    lower = valid(data.get("lower"))
    return upper, lower


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 3].rstrip() + "..."


def format_result(result: dict, show_text: bool = True) -> str:
    lines: list[str] = []
    verdict = result["verdict"]
    if verdict == VERDICT_FOUND:
        top = result["results"][0]
        lines.append(VERDICT_FOUND)
        lines.append(f"  {top['file']} > {top['heading']} ({top['score']:.3f})")
        if show_text:
            lines.append(f"  {_excerpt(top['text'])}")
        if len(result["results"]) > 1:
            lines.append("  also near:")
            for hit in result["results"][1:]:
                lines.append(
                    f"  {hit['file']} > {hit['heading']} ({hit['score']:.3f})"
                )
                if show_text:
                    lines.append(f"    {_excerpt(hit['text'])}")
    elif verdict == VERDICT_CHECK:
        top = result["results"][0]
        lines.append(VERDICT_CHECK)
        lines.append(f"  {top['file']} > {top['heading']} ({top['score']:.3f})")
        if show_text:
            lines.append(f"  {_excerpt(top['text'])}")
        lines.append("  A person should confirm this section answers the question.")
        if result.get("message"):
            lines.append(f"  {result['message']}")
    else:
        lines.append(VERDICT_NOT_FOUND)
        if result["results"]:
            lines.append("  closest, but not an answer:")
            for hit in result["results"]:
                lines.append(
                    f"  {hit['file']} > {hit['heading']} ({hit['score']:.3f})"
                )
                if show_text:
                    lines.append(f"    {_excerpt(hit['text'])}")
        if result.get("message"):
            lines.append(f"  {result['message']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------


def read_questions_csv(path: Path) -> list[dict]:
    """Read questions from a CSV with a question column and an optional label."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"No rows in {path}")
    if not any("question" in (row or {}) for row in rows):
        raise ValueError(f"{path} needs a 'question' column")
    cleaned = []
    for row in rows:
        row = {key.strip().lower(): (value or "").strip() for key, value in row.items()}
        question = row.get("question", "").strip()
        if not question:
            continue
        label = row.get("label", "").strip().lower()
        if label not in {"answerable", "unanswerable"}:
            label = ""
        cleaned.append({"question": question, "label": label})
    if not cleaned:
        raise ValueError(f"No questions found in {path}")
    return cleaned


def write_results_csv(
    rows: Sequence[dict], out_path: Path
) -> None:
    columns = list(RESULTS_COLUMNS)
    if rows and rows[0].get("label"):
        columns.insert(1, "label")
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            out = {column: row.get(column, "") for column in columns}
            writer.writerow(out)


def write_gaps_md(
    docs_label: str,
    rows: Sequence[dict],
    out_path: Path,
    cutoff_upper: float,
    cutoff_lower: float,
) -> None:
    """Write the gaps list: questions answered "Not in these documents",
    grouped by nearest section.

    Each group reads like a missing article: several questions landing near
    one section is a hint that the section exists but the answer does not.
    """
    selected = [
        row for row in rows if row["verdict"] == VERDICT_NOT_FOUND and row["results"]
    ]
    lines: list[str] = [
        f"# Gaps in {docs_label}",
        "",
        f"{len(selected)} of {len(rows)} questions are not answered by these "
        f"documents (lower cut-off {cutoff_lower:.3f}, upper cut-off "
        f"{cutoff_upper:.3f}).",
        "",
        "Each group below starts with the section that scored highest against",
        "those questions. A group with several questions under one section is",
        "a hint for an article that does not exist yet.",
        "",
    ]
    _append_grouped_sections(lines, selected, "Nothing on this list: every question was answered or sent to Check this.")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_check_this_md(
    docs_label: str,
    rows: Sequence[dict],
    out_path: Path,
    cutoff_upper: float,
    cutoff_lower: float,
) -> None:
    """Write the Check this list: questions between the two cut-offs.

    These questions scored too high to refuse and too low to answer, so a
    person should confirm the top section before anyone repeats it.
    """
    selected = [
        row for row in rows if row["verdict"] == VERDICT_CHECK and row["results"]
    ]
    lines: list[str] = [
        f"# Check this list for {docs_label}",
        "",
        f"{len(selected)} of {len(rows)} questions landed between the two "
        f"cut-offs (lower {cutoff_lower:.3f}, upper {cutoff_upper:.3f}).",
        "",
        "A person should confirm each of these. The section listed under a",
        "question is the one that scored highest; it sounds close, but it may",
        "not answer the question.",
        "",
    ]
    _append_grouped_sections(lines, selected, "Nothing on this list: no question landed between the cut-offs.")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _append_grouped_sections(lines: list[str], selected: Sequence[dict], empty_note: str) -> None:
    groups: dict[str, list[dict]] = {}
    for row in selected:
        top = row["results"][0]
        groups.setdefault(top["label"], []).append(row)

    ordered = sorted(
        groups.items(),
        key=lambda item: max(row["results"][0]["score"] for row in item[1]),
        reverse=True,
    )

    if not ordered:
        lines.append(empty_note)
        lines.append("")
        return
    for label, group_rows in ordered:
        lines.append(f"## {label}")
        lines.append("")
        for row in group_rows:
            score = row["results"][0]["score"]
            lines.append(f"- {row['question']} (score {score:.3f})")
        lines.append("")


def append_review_entry(
    docs_folder: Path, question: str, top: dict, verdict: str
) -> Path:
    """Single-question mode: add one line to the gaps or Check this list."""
    if verdict == VERDICT_CHECK:
        list_path = docs_folder / CHECK_NAME
        header = (
            f"# Check this list for {docs_folder}\n\n"
            "Questions between the two cut-offs, added one line at a time by"
            " single-question runs. A person should confirm each one:\n\n"
        )
    else:
        list_path = docs_folder / GAPS_NAME
        header = (
            f"# Gaps in {docs_folder}\n\n"
            "Questions these documents do not answer, added one line at a time"
            " by single-question runs:\n\n"
        )
    if not list_path.exists():
        list_path.write_text(header, encoding="utf-8")
    with list_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"- {question} (score {top['score']:.3f}, nearest: {top['label']})\n"
        )
    return list_path


def run_batch(
    index: DocumentIndex,
    questions: Sequence[dict],
    out_dir: Path,
    results_name: str = "results.csv",
    gaps_name: str = GAPS_NAME,
    check_name: str = CHECK_NAME,
) -> list[dict]:
    rows: list[dict] = []
    scores = index.score_all([item["question"] for item in questions])

    for position, item in enumerate(questions):
        row_scores = scores[position]
        order = np.argsort(-row_scores)[:DEFAULT_TOP_K]
        results = []
        for spot in order:
            chunk = index.chunks[int(spot)]
            results.append(
                {
                    "file": chunk.file,
                    "heading": chunk.heading,
                    "label": chunk.label,
                    "score": float(row_scores[int(spot)]),
                    "text": chunk.text,
                }
            )
        top_score = results[0]["score"] if results else 0.0
        if top_score >= index.cutoff_upper:
            verdict = VERDICT_FOUND
        elif top_score >= index.cutoff_lower:
            verdict = VERDICT_CHECK
        else:
            verdict = VERDICT_NOT_FOUND
        rows.append(
            {
                "question": item["question"],
                "label": item["label"],
                "verdict": verdict,
                "top_section": results[0]["label"] if results else "",
                "score": f"{results[0]['score']:.3f}" if results else "",
                "results": results,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    write_results_csv(rows, out_dir / results_name)
    write_gaps_md(
        str(index.docs_folder), rows, out_dir / gaps_name,
        index.cutoff_upper, index.cutoff_lower,
    )
    write_check_this_md(
        str(index.docs_folder), rows, out_dir / check_name,
        index.cutoff_upper, index.cutoff_lower,
    )
    return rows


def print_batch_summary(rows: Sequence[dict]) -> None:
    found = sum(1 for row in rows if row["verdict"] == VERDICT_FOUND)
    check = sum(1 for row in rows if row["verdict"] == VERDICT_CHECK)
    not_found = sum(1 for row in rows if row["verdict"] == VERDICT_NOT_FOUND)
    print(f"questions: {len(rows)}")
    print(f"found: {found}")
    print(f"check this: {check}")
    print(f"not in these documents: {not_found}")
    print("answers that said Found:")
    for row in rows:
        if row["verdict"] == VERDICT_FOUND:
            print(f"  {row['question']} -> {row['top_section']} ({row['score']})")
    print("answers that said Check this:")
    for row in rows:
        if row["verdict"] == VERDICT_CHECK:
            print(f"  {row['question']} -> {row['top_section']} ({row['score']})")
    print("answers that said Not in these documents:")
    for row in rows:
        if row["verdict"] == VERDICT_NOT_FOUND:
            print(f"  {row['question']} -> {row['top_section']} ({row['score']})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check a question against your documents, or add it to the gaps list."
    )
    parser.add_argument("docs_folder", help="Folder of .md, .txt, .html, .pdf or .docx files")
    parser.add_argument(
        "question",
        nargs="*",
        help="Question to ask (leave out when using --questions)",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=None,
        help="CSV file with a question column, for batch mode",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Where to write results.csv and gaps.md (default: next to the questions CSV)",
    )
    parser.add_argument(
        "--results-name", default="results.csv", help="Name of the results file"
    )
    parser.add_argument(
        "--upper",
        type=float,
        default=None,
        help="Upper cut-off: at or above it the verdict is Found "
        "(default: cutoff.json if present, else %(default)s)",
    )
    parser.add_argument(
        "--lower",
        type=float,
        default=None,
        help="Lower cut-off: below it the verdict is Not in these documents "
        "(default: cutoff.json if present, else %(default)s)",
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="How many chunks to show")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Sentence Transformers model")
    parser.add_argument("--cache-dir", default=None, help="Embedding cache folder")
    parser.add_argument(
        "--rebuild-cache", action="store_true", help="Ignore and replace the cache"
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=DEFAULT_MAX_WORDS,
        help=f"Chunk size in words (default: {DEFAULT_MAX_WORDS})",
    )
    parser.add_argument("--no-text", action="store_true", help="Hide chunk excerpts")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.questions is None and not args.question:
        parser.error("give a question, or --questions questions.csv")

    cutoff_upper = args.upper
    cutoff_lower = args.lower
    if cutoff_upper is None or cutoff_lower is None:
        saved_upper, saved_lower = load_saved_cutoffs(args.docs_folder)
        if cutoff_upper is None:
            cutoff_upper = saved_upper if saved_upper is not None else DEFAULT_CUTOFF_UPPER
        if cutoff_lower is None:
            cutoff_lower = saved_lower if saved_lower is not None else DEFAULT_CUTOFF_LOWER

    index = DocumentIndex.build(
        args.docs_folder,
        model_name=args.model,
        cache_dir=args.cache_dir,
        rebuild_cache=args.rebuild_cache,
        max_words=args.max_words,
        cutoff_upper=cutoff_upper,
        cutoff_lower=cutoff_lower,
    )

    if args.questions is None:
        question = " ".join(args.question)
        result = index.search(
            question, cutoff_upper=cutoff_upper, cutoff_lower=cutoff_lower,
            top_k=args.top_k,
        )
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(format_result(result, show_text=not args.no_text))
        if result["verdict"] in {VERDICT_NOT_FOUND, VERDICT_CHECK} and result["results"]:
            list_path = append_review_entry(
                index.docs_folder, question, result["results"][0], result["verdict"]
            )
            print(f"\nAdded to {list_path.name}: {list_path}")
        return 0

    questions = read_questions_csv(args.questions)
    out_dir = args.out_dir if args.out_dir is not None else args.questions.parent
    if args.out_dir is None and args.questions.parent.resolve() == index.docs_folder:
        # Do not drop generated files into the docs folder itself.
        out_dir = Path.cwd() / "show_me_output"
    rows = run_batch(
        index,
        questions,
        out_dir,
        results_name=args.results_name,
    )
    print(f"wrote {out_dir / args.results_name}")
    print(f"wrote {out_dir / 'gaps.md'}")
    print()
    print_batch_summary(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
