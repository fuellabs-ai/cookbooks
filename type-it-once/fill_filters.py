#!/usr/bin/env python3
"""Type it once, the filters fill in.

One typed sentence, for example "crimson trail shoes under 80, size 10,
waterproof", becomes a filter object whose values come only from the site's
own catalog, plus a small HTML page with the filter chips.

Who does what, by design:

1. Simple rules (regex plus a small built-in offline date parser) handle
   numbers, prices, sizes, guest counts and dates. No model involved.
2. A negation check runs before any matching: "no", "not" and "without"
   mask the words after them up to the next chunk boundary or number, so
   "no carpet" can never become carpet. Negated words stay in the output
   as search text, flagged.
3. HobbyLM-Embed matches the remaining phrases to the catalog's allowed
   values only ("crimson" to red, "seaside" to sea view). Model:
   harims95/hobbylm-embed-140m, revision ea708cee, trust_remote_code=True.
   Unit-norm vectors, dot product. User phrases are embedded with
   prompt_name="query" and value descriptions with prompt_name="passage".
4. Every value is validated against the catalog schema before output.
   A value that is not in the schema is never shown.
5. A match below the high threshold but above the low one becomes a grey
   "check this" chip, never a silent filter. Phrases that match nothing
   stay as plain search text, never dropped.

Usage:
    python fill_filters.py "crimson trail shoes under 80, size 10, waterproof" \
        --catalog examples/shoe_store/catalog.yaml
    python fill_filters.py --queries examples/shoe_store/queries_test.csv \
        --catalog examples/shoe_store/catalog.yaml --html chips.html

Thresholds come from examples/<name>/thresholds.json once calibrate.py has
run; --hi, --lo and --mode override them.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

import numpy as np
import yaml

DEFAULT_MODEL = "harims95/hobbylm-embed-140m"
MODEL_REVISION = "ea708cee"
DEFAULT_HI = 0.42
DEFAULT_LO = 0.32
DEFAULT_MARGIN = 0.05
DEFAULT_MODE = "prompt"
NEGATORS = {"no", "not", "without", "never", "none", "non"}
# words a negation scope never crosses: chunk boundaries, digits, and the
# prepositions and price comparators that start a rule match
SCOPE_BREAKERS = {
    "under", "below", "less", "up", "max", "around", "about", "than", "over",
    "from", "in", "on", "at", "of", "near", "per",
}
SPLIT_WORDS = {
    "and", "with", "for", "or", "but", "please", "also", "instead",
    "if", "possible", "though", "although", "however",
}
STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "of", "to", "is", "it", "its", "me",
    "my", "we", "us", "i", "you", "your", "some", "any", "that", "this",
    "these", "those", "be", "are", "was", "were", "do", "does", "would",
    "like", "want", "need", "looking", "get", "got", "there",
}
WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
GUEST_UNITS = r"(adults?|guests?|people|persons?|children|kids?)"
MAX_NEGATION_WORDS = 2
MAX_PHRASE_WORDS = 3


# ---------------------------------------------------------------------------
# Catalog


def load_catalog(path: Path) -> dict:
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    filters = catalog.get("filters")
    if not filters:
        raise ValueError(f"{path}: no filters found")
    for name, spec in filters.items():
        kind = spec.get("type")
        if kind not in {"enum", "number", "date"}:
            raise ValueError(f"{path}: filter {name} has unknown type {kind!r}")
        if kind == "enum" and len(spec.get("values") or []) < 2:
            raise ValueError(f"{path}: enum filter {name} needs 2+ values")
    return {"filters": filters, "name": path.parent.name}


def value_passages(catalog: dict) -> list[tuple[str, str, str]]:
    """(passage text, filter name, value) for every allowed enum value.

    The passage text is "filter_name: value", for example
    "room_type: family". Tested both ways on the dev split: with the filter
    name in the passage the word "room" in room_type pulls its weight for
    hotel queries, and without it (bare values) hotel dev accuracy drops.
    """
    out = []
    for name, spec in catalog["filters"].items():
        if spec["type"] != "enum":
            continue
        for value in spec["values"]:
            out.append((f"{name}: {value}", name, value))
    return out


def validate(filters: dict, catalog: dict) -> None:
    """Raise unless every filled filter and value exists in the schema."""
    schema = catalog["filters"]
    for name, values in filters.items():
        if name not in schema:
            raise ValueError(f"filter {name!r} is not in the catalog")
        spec = schema[name]
        if spec["type"] == "enum":
            allowed = set(spec["values"])
            bad = [v for v in values if v not in allowed]
            if bad:
                raise ValueError(f"values {bad} not allowed for {name}")
            if not spec.get("multi") and len(values) > 1:
                raise ValueError(f"{name} takes one value, got {values}")
        elif spec["type"] == "number":
            for v in values:
                if not spec["min"] <= v <= spec["max"]:
                    raise ValueError(f"value {v} out of range for {name}")
        elif spec["type"] == "date":
            for v in values:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)):
                    raise ValueError(f"date {v!r} is not ISO for {name}")


# ---------------------------------------------------------------------------
# Tokenising and negation


def tokenise(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end())
            for m in re.finditer(r"[^\W_]+", text, re.UNICODE)]


def negation_mask(
    tokens: Sequence[tuple[str, int, int]], enum_values: set[str]
) -> tuple[set[int], list[str]]:
    """Indices of negated words, and the negated phrases for the report.

    A negator masks the first content word after it, and a second one only
    when the first word alone is not itself a catalog value. So "no wifi"
    and "not suede" mask one word, "without a wide fit" and "not sea view"
    mask two, and in "not black running shoes" only "black" is masked, so
    "running shoes" survives. Case insensitive: "no Balcony" masks
    "Balcony". A chunk boundary (split word, digit, punctuation such as a
    comma, or a price comparator) always ends the scope.
    """
    masked: set[int] = set()
    phrases: list[str] = []
    i = 0
    while i < len(tokens):
        word = tokens[i][0].lower()
        if word in NEGATORS:
            scope: list[int] = []
            j = i + 1
            first: int | None = None
            while j < len(tokens) and len(scope) < 4:
                w = tokens[j][0]
                lw = w.lower()
                if lw in SPLIT_WORDS or lw in SCOPE_BREAKERS or any(c.isdigit() for c in w):
                    break
                if j > 0 and tokens[j][1] - tokens[j - 1][2] > 1:
                    break  # punctuation between the words: new chunk
                if lw in STOP_WORDS:
                    scope.append(j)
                    j += 1
                    continue
                if first is None:
                    first = j
                    scope.append(j)
                    j += 1
                    continue
                # second content word: only when the first is not a value
                if tokens[first][0].lower() not in enum_values:
                    scope.append(j)
                break
            if scope:
                masked.update(scope)
                phrases.append(" ".join(tokens[k][0] for k in scope))
            i = max(j, i + 1)
        else:
            i += 1
    return masked, phrases


# ---------------------------------------------------------------------------
# Rules: dates, sizes, guest counts, nights, prices


def _num(word: str) -> int | None:
    if word.isdigit():
        return int(word)
    return WORD_NUMBERS.get(word.lower())


def parse_dates(tokens, today: date) -> list[dict]:
    """Small offline date parser, relative to the --today base date."""
    fills = []
    lows = [t[0].lower() for t in tokens]

    def add(words: list[int], value: date, rule: str, nights: int | None = None):
        fills.append({"filter": "checkin", "value": value.isoformat(),
                      "tokens": list(words), "rule": rule})
        if nights is not None:
            fills.append({"filter": "nights", "value": nights,
                          "tokens": list(words), "rule": rule})

    i = 0
    while i < len(tokens):
        w = lows[i]
        if w in {"today", "tonight"}:
            add([i], today, "today/tonight")
            i += 1
            continue
        if w == "tomorrow":
            add([i], today + timedelta(days=1), "tomorrow")
            i += 1
            continue
        if w == "weekend":
            start = i - 1 if i > 0 and lows[i - 1] in {"this", "next", "a", "the"} else i
            offset = 7 if start < i and lows[start] == "next" else 0
            days = (5 - today.weekday()) % 7 + offset
            add(list(range(start, i + 1)), today + timedelta(days=days), "weekend", nights=2)
            i += 1
            continue
        if w == "week":
            start = i - 1 if i > 0 and lows[i - 1] in {"a", "one", "this", "the"} else i
            fills.append({"filter": "nights", "value": 7,
                          "tokens": list(range(start, i + 1)), "rule": "a week"})
            i += 1
            continue
        wd = WEEKDAYS.get(w)
        if wd is not None:
            start = i - 1 if i > 0 and lows[i - 1] in {"this", "next", "on", "the"} else i
            qualifier = lows[start] if start < i else ""
            days = (wd - today.weekday()) % 7
            if qualifier == "next":
                days += 7
            add(list(range(start, i + 1)), today + timedelta(days=days), "weekday")
            i += 1
            continue
        m = re.fullmatch(r"(\d{1,2})(st|nd|rd|th)?", w)
        if m and i + 1 < len(tokens) and lows[i + 1][:3] in MONTHS:
            if _day_month(m.group(1), MONTHS[lows[i + 1][:3]], today):
                add([i, i + 1], _day_month(m.group(1), MONTHS[lows[i + 1][:3]], today), "day month")
                i += 2
                continue
        if w[:3] in MONTHS and i + 1 < len(tokens) and re.fullmatch(r"\d{1,2}", lows[i + 1]):
            d = _day_month(lows[i + 1], MONTHS[w[:3]], today)
            if d:
                add([i, i + 1], d, "month day")
                i += 2
                continue
        if w == "in" and i + 2 < len(tokens) and lows[i + 2].rstrip("s") == "day":
            n = _num(lows[i + 1])
            if n is not None:
                add([i, i + 1, i + 2], today + timedelta(days=n), "in N days")
                i += 3
                continue
        i += 1
    return fills


def _day_month(day: str, month: int, today: date) -> date | None:
    try:
        d = date(today.year, month, int(day))
    except ValueError:
        return None
    if d < today:
        try:
            d = date(today.year + 1, month, int(day))
        except ValueError:
            return None
    return d


def parse_numbers(tokens, catalog: dict, taken: set[int]) -> tuple[list[dict], set[int]]:
    """Sizes, guest counts, nights and prices. Rules claim their tokens."""
    fills: list[dict] = []
    lows = [t[0].lower() for t in tokens]
    filters = catalog["filters"]

    def claim(indices: list[int], filter_name: str, value, rule: str):
        if filter_name in filters:
            fills.append({"filter": filter_name, "value": value,
                          "tokens": list(indices), "rule": rule})
        taken.update(indices)

    i = 0
    while i < len(tokens):
        if i in taken:
            i += 1
            continue
        w = lows[i]
        nxt = lows[i + 1] if i + 1 < len(tokens) else ""
        after = lows[i + 2] if i + 2 < len(tokens) else ""
        # size: "size 10", "uk 11", "eu 44", "us 9", and the trailing unit
        # word in "size 10 uk"
        if re.fullmatch(r"(size|uk|eu|us)", w) and re.fullmatch(r"\d{1,2}", nxt):
            end = i + 2
            if end < len(tokens) and lows[end] in {"uk", "eu", "us"}:
                end += 1
            claim(list(range(i, end)), "size_uk", int(nxt), "size")
            i = end
            continue
        n = _num(w)
        # guests: "2 adults", "two children", "family of 4", "sleeping 4", "for 2"
        if n is not None and re.match(GUEST_UNITS, nxt):
            claim([i, i + 1], "guests", n, "guest count")
            i += 2
            continue
        if w == "family" and nxt == "of" and _num(after) is not None:
            claim([i, i + 1, i + 2], "guests", _num(after), "family of N")
            i += 3
            continue
        if w == "sleeping" and _num(nxt) is not None:
            claim([i, i + 1], "guests", _num(nxt), "sleeping N")
            i += 2
            continue
        if w == "for" and _num(nxt) is not None and not re.match(
            r"(nights?|rooms?|adults?|guests?|people|persons?|children|kids?|days?)", after
        ):
            claim([i, i + 1], "guests", _num(nxt), "for N")
            i += 2
            continue
        if w == "couple":
            claim([i], "guests", 2, "couple")
            i += 1
            continue
        # nights: "3 nights", "two nights"
        if n is not None and re.match(r"nights?\b", nxt):
            claim([i, i + 1], "nights", n, "N nights")
            i += 2
            continue
        # price: comparators and currency
        if re.fullmatch(r"(under|below|less|up|max|around|about)", w):
            j = i + 1 + (1 if nxt == "than" else 0)
            if j < len(tokens) and re.fullmatch(r"[£$€]?(\d+)", lows[j]):
                value = int(lows[j].lstrip("£$€"))
                claim(list(range(i, j + 1)), "price_max", value, "price")
                i = j + 1
                continue
        if re.fullmatch(r"[£$€]\d+", w):
            claim([i], "price_max", int(w[1:]), "price")
            i += 1
            continue
        if n is not None and re.match(r"(dollars|euros|pounds|quid|bucks)\b", nxt):
            claim([i, i + 1], "price_max", n, "price")
            i += 2
            continue
        i += 1
    return fills, taken


# ---------------------------------------------------------------------------
# Model


def load_model(model_name: str = DEFAULT_MODEL):
    import warnings
    warnings.filterwarnings("ignore")
    import transformers
    transformers.logging.set_verbosity_error()
    transformers.utils.logging.disable_progress_bar()
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        model_name, revision=MODEL_REVISION, trust_remote_code=True, device="cpu"
    )


def _norm(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-9)


def embed_values(texts: Sequence[str], model, mode: str) -> np.ndarray:
    if mode == "prompt":
        return _norm(model.encode(list(texts), prompt_name="passage",
                                  convert_to_numpy=True))
    return _norm(model.encode(list(texts), convert_to_numpy=True))


def embed_queries(texts: Sequence[str], model, mode: str) -> np.ndarray:
    if mode == "prompt":
        return _norm(model.encode(list(texts), prompt_name="query",
                                  convert_to_numpy=True))
    return _norm(model.encode(list(texts), convert_to_numpy=True))


# ---------------------------------------------------------------------------
# Analyse (threshold independent) and assign (threshold dependent)


def analyse(
    text: str,
    catalog: dict,
    model,
    value_matrix: dict[str, np.ndarray],
    filter_values: dict[str, list[str]],
    mode: str,
    today: date,
) -> dict:
    tokens = tokenise(text)
    enum_values = {
        v.lower()
        for spec in catalog["filters"].values() if spec["type"] == "enum"
        for v in spec["values"]
    }
    masked, negated = negation_mask(tokens, enum_values)
    negators = {
        i for i, t in enumerate(tokens) if t[0].lower() in NEGATORS
    }

    rule_fills: list[dict] = []
    taken: set[int] = set(masked) | negators
    for fill in parse_dates(tokens, today):
        if any(i in masked for i in fill["tokens"]):
            continue
        rule_fills.append(fill)
        taken.update(fill["tokens"])
    number_fills, taken = parse_numbers(tokens, catalog, taken)
    rule_fills.extend(number_fills)

    # a rule fill that the schema refuses falls back to search text
    valid_fills: list[dict] = []
    for fill in rule_fills:
        spec = catalog["filters"].get(fill["filter"])
        ok = spec is not None and (
            spec["type"] != "number"
            or spec["min"] <= fill["value"] <= spec["max"]
        )
        if ok:
            valid_fills.append(fill)
        else:
            taken.difference_update(fill["tokens"])
    rule_fills = valid_fills

    rule_filters: dict[str, list] = {}
    seen: set = set()
    for fill in rule_fills:
        key = (fill["filter"], json.dumps(fill["value"], sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        rule_filters.setdefault(fill["filter"], []).append(fill["value"])

    free = set(range(len(tokens))) - taken
    name_words = {
        w for name in catalog["filters"] for w in re.findall(r"[^\W_]+", name)
    }
    phrases = candidate_phrases(tokens, free, name_words)
    candidates: list[dict] = []
    if phrases and value_matrix:
        vectors = embed_queries([p for p, _ in phrases], model, mode)
        for (phrase, span), vec in zip(phrases, vectors):
            tops = []
            for name, matrix in value_matrix.items():
                sims = matrix @ vec
                top = int(np.argmax(sims))
                tops.append((float(sims[top]), name, filter_values[name][top]))
            tops.sort(key=lambda t: -t[0])
            best = tops[0]
            runner = tops[1][0] if len(tops) > 1 else -1.0
            candidates.append({
                "phrase": phrase, "span": list(span), "filter": best[1],
                "value": best[2], "score": round(best[0], 3),
                "margin": round(best[0] - runner, 3),
            })
    candidates.sort(key=lambda c: -c["score"])
    return {
        "tokens": tokens, "negated": negated, "rule_fills": rule_fills,
        "rule_filters": rule_filters, "candidates": candidates,
    }


def assign(analysis: dict, catalog: dict, hi: float, lo: float,
           margin: float) -> tuple[dict, list[dict], str]:
    """Greedy assignment: every word fills at most one filter, highest wins.

    A phrase fills only when its score clears the high threshold AND its
    margin over the runner-up value clears the margin. Otherwise, if the
    score clears the low threshold, it becomes a grey check-this chip.
    Below the low threshold it stays as plain search text.
    """
    filters: dict[str, list] = {k: list(v) for k, v in analysis["rule_filters"].items()}
    used: set[int] = set()
    check: list[dict] = []
    for cand in analysis["candidates"]:
        span = cand["span"]
        if any(i in used for i in span):
            continue
        spec = catalog["filters"][cand["filter"]]
        single = not spec.get("multi")
        filled = filters.get(cand["filter"])
        if cand["score"] >= hi and cand["margin"] >= margin and (not filled or not single):
            filters.setdefault(cand["filter"], []).append(cand["value"])
            used.update(span)
        elif cand["score"] >= lo and (not filled or not single):
            # a check-this chip is a suggestion: it does not claim the words,
            # so a later, better unigram can still fill its filter
            check.append(cand)
    tokens = analysis["tokens"]
    search_text = " ".join(
        tokens[i][0] for i in sorted(set(range(len(tokens))) - used)
        if tokens[i][0].lower() not in SPLIT_WORDS
        and i not in {t for c in analysis["rule_fills"] for t in c["tokens"]}
    )
    return filters, check, search_text


def match_query(
    text: str,
    catalog: dict,
    analysis: dict,
    hi: float,
    lo: float,
    margin: float,
) -> dict:
    filters, check, search_text = assign(analysis, catalog, hi, lo, margin)
    filters = {k: v for k, v in filters.items() if v}
    validate(filters, catalog)
    return {
        "query": text,
        "filters": filters,
        "check": [
            {"phrase": c["phrase"], "filter": c["filter"],
             "value": c["value"], "score": c["score"]}
            for c in check
        ],
        "search_text": search_text,
        "negated": analysis["negated"],
        "rule_fills": [
            {"filter": f["filter"], "value": f["value"], "rule": f["rule"]}
            for f in analysis["rule_fills"]
        ],
    }


def candidate_phrases(tokens, free: set[int], name_words: set[str]) -> list[tuple[str, list[int]]]:
    """Contiguous 1..3 word phrases inside chunk boundaries, on free words.

    A chunk break is a split word, or punctuation between two words
    (for example the comma in "sea view, garden view"). A phrase whose every
    content word is a filter-name word ("room" in room_type, "view" in view,
    plurals included) is skipped: those words name the filters, they are not
    search phrases.
    """
    words = [tokens[i][0].lower() for i in range(len(tokens))]

    def is_name_word(w: str) -> bool:
        return w in name_words or w.rstrip("s") in name_words

    chunks: list[list[int]] = []
    current: list[int] = []
    prev_index: int | None = None
    for i in sorted(free):
        if words[i] in SPLIT_WORDS:
            if current:
                chunks.append(current)
            current = []
        elif prev_index is not None and tokens[i][1] - tokens[prev_index][2] > 1:
            if current:
                chunks.append(current)
            current = [i]
        else:
            current.append(i)
        prev_index = i
    if current:
        chunks.append(current)
    out = []
    for chunk in chunks:
        for size in (MAX_PHRASE_WORDS, 2, 1):
            for start in range(0, len(chunk) - size + 1):
                span = chunk[start:start + size]
                phrase_words = [words[i] for i in span]
                content = [w for w in phrase_words if w not in STOP_WORDS]
                if not content:
                    continue
                if all(is_name_word(w) for w in content):
                    continue
                out.append((" ".join(phrase_words), span))
    return out


class Matcher:
    """Catalog values embedded once, reused across queries and sweeps."""

    def __init__(self, catalog: dict, model, mode: str):
        self.catalog = catalog
        self.model = model
        self.mode = mode
        passages = value_passages(catalog)
        by_filter: dict[str, list[int]] = {}
        for i, (_p, name, _v) in enumerate(passages):
            by_filter.setdefault(name, []).append(i)
        vectors = embed_values([p for p, _, _ in passages], model, mode)
        self.value_matrix = {name: vectors[idx] for name, idx in by_filter.items()}
        self.filter_values = {
            name: [passages[i][2] for i in idx] for name, idx in by_filter.items()
        }

    def analyse(self, text: str, today: date) -> dict:
        return analyse(text, self.catalog, self.model, self.value_matrix,
                       self.filter_values, self.mode, today)

    def match(self, text: str, today: date, hi: float, lo: float,
              margin: float) -> dict:
        return match_query(text, self.catalog, self.analyse(text, today),
                           hi, lo, margin)


# ---------------------------------------------------------------------------
# Output


def load_settings(catalog_path: Path, hi: float | None, lo: float | None,
                  mode: str | None, margin: float | None) -> dict:
    settings = {"mode": DEFAULT_MODE, "hi": DEFAULT_HI, "lo": DEFAULT_LO,
                "margin": DEFAULT_MARGIN}
    thresholds = catalog_path.parent / "thresholds.json"
    if thresholds.exists():
        saved = json.loads(thresholds.read_text(encoding="utf-8"))
        settings.update({k: saved[k] for k in ("mode", "hi", "lo", "margin")
                         if k in saved})
    if mode:
        settings["mode"] = mode
    if hi is not None:
        settings["hi"] = hi
    if lo is not None:
        settings["lo"] = lo
    if margin is not None:
        settings["margin"] = margin
    return settings


CHIP_STYLES = """
body{font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;max-width:720px;margin:24px auto;padding:0 16px;color:#1a1a24;}
h1{font-size:20px;} .q{font-size:16px;margin:18px 0 8px;font-weight:600;}
.chip{display:inline-block;border-radius:14px;padding:3px 12px;margin:2px 4px 2px 0;font-size:13px;}
.fill{background:#e3f4e3;border:1px solid #9ccc9c;}
.grey{background:#f0f0f2;border:1px solid #c9c9d2;color:#555;}
.plain{color:#666;font-size:13px;margin-top:6px;}
.negated{color:#a33;font-size:13px;text-decoration:line-through;margin-top:4px;}
.rule{color:#888;font-size:12px;margin-top:4px;}
"""


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


def build_html(results: Sequence[dict]) -> str:
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Type it once, the filters fill in</title>"
        f"<style>{CHIP_STYLES}</style></head><body>",
        "<h1>Type it once, the filters fill in</h1>",
        "<p class='plain'>Sample data. Green chips filled a filter from the "
        "catalog; grey chips say check this; struck words were negated; the "
        "plain line is left-over search text.</p>",
    ]
    for r in results:
        parts.append(f"<p class='q'>{_esc(r['query'])}</p><div>")
        for name, values in r["filters"].items():
            for v in values:
                parts.append(f"<span class='chip fill'>{_esc(name)}: {_esc(v)}</span>")
        for c in r["check"]:
            parts.append(
                f"<span class='chip grey'>check this: {_esc(c['phrase'])} "
                f"(&rarr; {_esc(c['filter'])}: {_esc(c['value'])} "
                f"{c['score']:.2f})</span>"
            )
        parts.append("</div>")
        if r["negated"]:
            parts.append(
                f"<p class='negated'>negated: {_esc(', '.join(r['negated']))}</p>"
            )
        if r["search_text"]:
            parts.append(f"<p class='plain'>search text: {_esc(r['search_text'])}</p>")
        if r["rule_fills"]:
            rules = ", ".join(
                f"{f['filter']}={f['value']} ({f['rule']})" for f in r["rule_fills"]
            )
            parts.append(f"<p class='rule'>rules: {_esc(rules)}</p>")
    parts.append("</body></html>")
    return "".join(parts)


def evaluate_batch(rows: Sequence[dict], results: Sequence[dict]) -> dict:
    """Compare filled filters against expected. Check-this chips are not fills."""
    correct = 0
    misses = []
    chip_hits = 0
    false_fills = 0
    missed_fills = 0
    for row, res in zip(rows, results):
        expected = json.loads(row["expected"]) if row.get("expected") else {}
        exp = {k: sorted(_canon(x) for x in v) for k, v in expected.items()}
        got = {k: sorted(_canon(x) for x in v) for k, v in res["filters"].items()}
        if got == exp:
            correct += 1
        else:
            extra = {k: v for k, v in got.items() if exp.get(k) != v}
            missing = {k: v for k, v in exp.items() if got.get(k) != v}
            false_fills += sum(len(v) for v in extra.values())
            missed_fills += sum(
                len(set(v) - set(got.get(k, []))) for k, v in missing.items()
            )
            misses.append({
                "id": row.get("id", ""), "query": row["text"],
                "expected": expected, "got": res["filters"],
            })
        for c in res["check"]:
            if c["value"] in [str(x) for x in expected.get(c["filter"], [])]:
                chip_hits += 1
    n = len(rows)
    return {
        "queries": n, "correct": correct, "wrong": n - correct,
        "misses": misses, "correct_share": round(correct / n, 3) if n else 0.0,
        "chip_hits": chip_hits, "false_fills": false_fills,
        "missed_fills": missed_fills,
    }


def _canon(x):
    return round(float(x), 4) if isinstance(x, (int, float)) else x


def print_report(report: dict) -> None:
    print(
        f"{report['queries']} queries, fully correct: {report['correct']}"
        f"/{report['queries']} ({report['correct_share']:.0%}), "
        f"wrong: {report['wrong']}, right value offered as a chip: "
        f"{report['chip_hits']}"
    )
    for m in report["misses"]:
        print(f"  miss {m['id']}: {m['query']}")
        print(f"    expected: {json.dumps(m['expected'], sort_keys=True)}")
        print(f"    got:      {json.dumps(m['got'], sort_keys=True)}")


# ---------------------------------------------------------------------------
# CLI


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fill a site's search filters from one typed sentence."
    )
    parser.add_argument("query", nargs="?", default=None, help="One sentence")
    parser.add_argument("--catalog", required=True, help="catalog.yaml path")
    parser.add_argument("--queries", default=None, help="CSV with text column for batch mode")
    parser.add_argument("--today", default=None, help="Base date YYYY-MM-DD for relative dates")
    parser.add_argument("--hi", type=float, default=None, help="Fill threshold")
    parser.add_argument("--lo", type=float, default=None, help="Check-this threshold")
    parser.add_argument("--margin", type=float, default=None,
                        help="Margin a fill must beat the runner-up value by")
    parser.add_argument("--mode", choices=["prompt", "plain"], default=None)
    parser.add_argument("--html", default=None, help="Write the chip page here")
    parser.add_argument("--out", default=None, help="Write batch results JSON here")
    args = parser.parse_args(argv)

    catalog = load_catalog(Path(args.catalog))
    settings = load_settings(Path(args.catalog), args.hi, args.lo, args.mode,
                             args.margin)
    today = date.fromisoformat(args.today) if args.today else date.today()

    if args.queries:
        with open(args.queries, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        model = load_model()
        matcher = Matcher(catalog, model, settings["mode"])
        results = [
            matcher.match(r["text"], today, settings["hi"], settings["lo"],
                          settings["margin"])
            for r in rows
        ]
        report = evaluate_batch(rows, results)
        if args.html:
            Path(args.html).write_text(build_html(results), encoding="utf-8")
        if args.out:
            Path(args.out).write_text(
                json.dumps({"settings": settings, "report": report,
                            "results": results}, indent=1, ensure_ascii=False),
                encoding="utf-8",
            )
        print(
            f"{report['queries']} queries, mode {settings['mode']}, "
            f"hi {settings['hi']}, lo {settings['lo']}, "
            f"margin {settings['margin']}"
        )
        print_report(report)
        return 0

    if not args.query:
        parser.error("give a sentence or --queries")
    model = load_model()
    matcher = Matcher(catalog, model, settings["mode"])
    result = matcher.match(args.query, today, settings["hi"], settings["lo"],
                           settings["margin"])
    if args.html:
        Path(args.html).write_text(build_html([result]), encoding="utf-8")
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
