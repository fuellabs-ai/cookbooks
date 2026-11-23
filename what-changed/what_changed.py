#!/usr/bin/env python3
"""What really changed? Compare two versions of a document by meaning.

A HobbyLM-Embed cookbook recipe. Embeddings only, no LLM.

    python what_changed.py old.txt new.txt [--show-all] [--threshold 0.90]

Model: harims95/hobbylm-embed-140m via Sentence Transformers
(trust_remote_code=True). The model turns each clause into a normalized
512-dimensional vector, so similarity is a plain dot product.

This is a similarity job, not a search job: clauses are embedded as plain
text with no query/passage prompt prefixes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict

import numpy as np

MODEL_ID = "harims95/hobbylm-embed-140m"
MODEL_REVISION = "ea708cee107818fa0c1871eebd26d82a1e3fb1aa"
DEFAULT_MAX_TOKENS = 512  # the model reads 512 tokens by default
MAX_TOKEN_LIMIT = 2048    # up to 2,048 if you raise the limit

DEFAULT_THRESHOLD = 0.85  # reworded vs changed; midpoint of the gap observed on examples/
DEFAULT_FLOOR = 0.74      # below this a clause has no close match at all

# Risky phrases. If one is added, removed or swapped inside a matched pair,
# the pair counts as Changed even when the similarity is high. Negation words
# collapse into one class so "no X" -> "without X" stays a rewording, while
# "not included" -> "included" does not.
DEFAULT_CLAIM_WORDS = [
    "may contain", "contains", "free", "guaranteed", "up to", "at least",
    "unlimited", "high in", "source of", "certified", "no longer",
    "not", "no", "without",
]
NEGATION_CLASS = {"not", "no", "no longer", "without"}

MONTHS = {
    "jan": "January", "feb": "February", "mar": "March", "apr": "April",
    "may": "May", "jun": "June", "jul": "July", "aug": "August",
    "sep": "September", "sept": "September", "oct": "October",
    "nov": "November", "dec": "December",
    "january": "January", "february": "February", "march": "March",
    "april": "April", "june": "June", "july": "July", "august": "August",
    "september": "September", "october": "October", "november": "November",
    "december": "December",
}
MONTH_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
PRICE_RE = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d+)?")
PERCENT_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s?%|\b\d[\d,]*(?:\.\d+)? percent\b", re.IGNORECASE)


def normalize(text: str) -> str:
    """Collapse whitespace for exact-match comparison."""
    return re.sub(r"\s+", " ", text).strip()


def split_clauses(text: str) -> list[str]:
    """Split a document into clauses: bullet lines and sentences.

    Keeps each clause short; the model reads 512 tokens by default, up to
    2,048 if you raise the limit, and short clauses match far better than
    long paragraphs.
    """
    clauses: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Strip markdown heading markers and bullet markers.
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^[-*•]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        if not line:
            continue
        # Sentence split: punctuation, whitespace, then a new capital or digit.
        pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9$(])", line)
        for piece in pieces:
            piece = normalize(piece)
            if piece:
                clauses.append(piece)
    return clauses


def extract_claims(text: str, claim_words=None) -> Counter:
    """Risky claim phrases in a clause, counted by phrase.

    Complements the number check: "high in fiber" and "good source of fiber"
    embed almost the same and carry no numbers, but swap a claim word.
    """
    if claim_words is None:
        claim_words = DEFAULT_CLAIM_WORDS
    t = text.lower()
    claims: Counter = Counter()
    for phrase in claim_words:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        n = len(re.findall(pattern, t))
        if n:
            key = "negation" if phrase in NEGATION_CLASS else phrase
            claims[key] += n
            t = re.sub(pattern, " ", t)
    return claims


def extract_facts(text: str) -> Counter:
    """Numbers, prices, dates, percentages and durations in a clause.

    Used to catch meaning flips that embeddings score as rewordings:
    "30 days" and "60 days" are nearly the same to any embedder.
    """
    facts: list[str] = []
    months = [MONTHS[m.lower()] for m in MONTH_RE.findall(text)]
    facts.extend(months)
    # Prices and percentages are taken out of the text before plain
    # numbers are counted, so their digits are not counted twice.
    prices = [p.replace(" ", "") for p in PRICE_RE.findall(text)]
    facts.extend(prices)
    text = PRICE_RE.sub(" ", text)
    percents = [p.replace(" ", "") for p in PERCENT_RE.findall(text)]
    facts.extend(percents)
    text = PERCENT_RE.sub(" ", text)
    numbers = NUMBER_RE.findall(text)
    facts.extend(numbers)
    return Counter(facts)


def counter_diff(old_counts: Counter, new_counts: Counter) -> str | None:
    """Human-readable summary of which counted items differ between two clauses."""
    only_old = old_counts - new_counts
    only_new = new_counts - old_counts
    if not only_old and not only_new:
        return None
    old_list = [f for f, n in sorted(only_old.items(), key=fact_sort_key) for _ in range(n)]
    new_list = [f for f, n in sorted(only_new.items(), key=fact_sort_key) for _ in range(n)]
    return f"old: {', '.join(old_list) or 'none'} | new: {', '.join(new_list) or 'none'}"


fact_diff = counter_diff  # the number-check summary uses the same logic


def fact_sort_key(item):
    text, _count = item
    stripped = text.lstrip("$€£")
    try:
        return (0, float(stripped.replace(",", "")), "")
    except ValueError:
        return (1, 0.0, text)


class Pair:
    __slots__ = ("label", "old", "new", "sim", "reason")

    def __init__(self, label, old, new, sim, reason):
        self.label = label  # unchanged | reworded | changed | added | removed
        self.old = old
        self.new = new
        self.sim = sim
        self.reason = reason


def compare(old_text: str, new_text: str, model, threshold: float, floor: float,
            max_tokens: int = DEFAULT_MAX_TOKENS,
            claim_check: bool = True, claim_words=None):
    """Match clauses across versions and label every pair."""
    old_clauses = split_clauses(old_text)
    new_clauses = split_clauses(new_text)

    # Warn about clauses the model would have to truncate.
    for clause in old_clauses + new_clauses:
        n_tokens = len(model.tokenizer(clause, add_special_tokens=False)["input_ids"])
        if n_tokens > max_tokens:
            print(f"warning: clause over {max_tokens} tokens will be truncated: {clause[:80]}...",
                  file=sys.stderr)

    pairs: list[Pair] = []

    # 1. Exact matches are Unchanged, no embedding needed.
    old_by_text: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(old_clauses):
        old_by_text[normalize(c).lower()].append(i)
    old_exact, new_exact = set(), set()
    for j, c in enumerate(new_clauses):
        key = normalize(c).lower()
        if old_by_text[key]:
            i = old_by_text[key].pop()
            old_exact.add(i)
            new_exact.add(j)
            pairs.append(Pair("unchanged", old_clauses[i], c, 1.0, "identical text"))

    # 2. Everything else: embed as plain text (no prompts) and match greedily.
    old_rest = [i for i in range(len(old_clauses)) if i not in old_exact]
    new_rest = [j for j in range(len(new_clauses)) if j not in new_exact]
    if old_rest and new_rest:
        old_vecs = model.encode(old_clauses, normalize_embeddings=True)
        new_vecs = model.encode(new_clauses, normalize_embeddings=True)
        old_facts = [extract_facts(old_clauses[i]) for i in old_rest]
        old_claims = [extract_claims(old_clauses[i], claim_words) for i in old_rest] if claim_check else None
        sim = old_vecs[old_rest] @ new_vecs[new_rest].T  # vectors are unit length

        taken_old, taken_new = set(), set()
        order = np.argsort(sim.ravel())[::-1]
        for flat in order:
            a, b = divmod(int(flat), sim.shape[1])
            if sim[a, b] < floor:
                break
            if a in taken_old or b in taken_new:
                continue
            i, j = old_rest[a], new_rest[b]
            score = float(sim[a, b])
            # Below the reword threshold, a pair must be the overall nearest
            # match of both sides across the whole other document. Otherwise
            # two unrelated leftovers grab each other and a genuinely
            # removed clause shows up as a fake Changed pair.
            if score < threshold:
                best_old_for_j = int(np.argmax(old_vecs @ new_vecs[j]))
                best_new_for_i = int(np.argmax(new_vecs @ old_vecs[i]))
                if best_old_for_j != i or best_new_for_i != j:
                    continue
            taken_old.add(a)
            taken_new.add(b)
            diff = counter_diff(old_facts[a], extract_facts(new_clauses[j]))
            claim_diff = None
            if claim_check:
                claim_diff = counter_diff(old_claims[a], extract_claims(new_clauses[j], claim_words))
            if diff:
                pairs.append(Pair("changed", old_clauses[i], new_clauses[j], score,
                                  f"numbers/dates differ ({diff})"))
            elif claim_diff:
                pairs.append(Pair("changed", old_clauses[i], new_clauses[j], score,
                                  f"claim words differ ({claim_diff})"))
            elif score >= threshold:
                pairs.append(Pair("reworded", old_clauses[i], new_clauses[j], score,
                                  "same meaning, different words"))
            else:
                pairs.append(Pair("changed", old_clauses[i], new_clauses[j], score,
                                  f"related but sim {score:.2f} < {threshold:.2f}"))
        # 3. Whatever never found a close partner is Added or Removed.
        for a in range(len(old_rest)):
            if a not in taken_old:
                pairs.append(Pair("removed", old_clauses[old_rest[a]], None, None, "no close match in new"))
        for b in range(len(new_rest)):
            if b not in taken_new:
                pairs.append(Pair("added", None, new_clauses[new_rest[b]], None, "no close match in old"))
    else:
        for i in old_rest:
            pairs.append(Pair("removed", old_clauses[i], None, None, "no close match in new"))
        for j in new_rest:
            pairs.append(Pair("added", None, new_clauses[j], None, "no close match in old"))

    return pairs


LABEL_ORDER = ["changed", "added", "removed", "reworded", "unchanged"]
LABEL_COUNTS_ORDER = ["unchanged", "reworded", "changed", "added", "removed"]


def eval_hard_cases(csv_path, model, threshold, floor, claim_check=True, claim_words=None,
                    max_tokens=DEFAULT_MAX_TOKENS, show_pairs=True):
    """Label each old/new pair in a CSV and score against the expected label.

    The CSV needs columns old, new, expected. An empty new cell means the old
    clause was removed. Expected labels: changed or removed.
    """
    import csv
    rows = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append((row["old"].strip(), row["new"].strip(), row["expected"].strip()))
    results = []
    for old, new, expected in rows:
        pairs = compare(old, new, model, threshold, floor, max_tokens,
                        claim_check=claim_check, claim_words=claim_words)
        predicted = pairs[0].label if pairs else "unchanged"
        reason = pairs[0].reason if pairs else ""
        sim = pairs[0].sim if pairs else None
        results.append((old, new, expected, predicted, sim, reason))
    hits = sum(1 for r in results if r[2] == r[3])
    print(f"HARD CASES: {csv_path}")
    if show_pairs:
        for k, (old, new, expected, predicted, sim, reason) in enumerate(results, 1):
            mark = "ok  " if expected == predicted else "MISS"
            sim_text = f"sim {sim:.2f}, " if sim is not None else ""
            new_text = new if new else "(empty, clause removed)"
            print(f"{k}. [{mark}] expected {expected}, predicted {predicted} ({sim_text}{reason})")
            print(f"   old: {old}")
            print(f"   new: {new_text}")
    print(f"accuracy: {hits}/{len(results)} = {hits / len(results):.0%}")
    print("")
    return hits, len(results)


def render_report(pairs: list[Pair], old_path, new_path, model_id, threshold, floor, show_all):
    lines = []
    counts = Counter(p.label for p in pairs)
    lines.append("WHAT REALLY CHANGED")
    lines.append(f"old: {old_path}")
    lines.append(f"new: {new_path}")
    lines.append(f"model: {model_id} | reword threshold {threshold:.2f} | related floor {floor:.2f}")
    lines.append("")
    lines.append("COUNTS")
    for label in LABEL_COUNTS_ORDER:
        note = ""
        if label == "reworded" and counts[label] and not show_all:
            note = "  (hidden, run with --show-all to see them)"
        lines.append(f"{label:<10} {counts[label]:>3}{note}")
    lines.append("")

    def clause_text(pair, side):
        text = pair.old if side == "old" else pair.new
        return text if text is not None else "(none)"

    for label in LABEL_ORDER:
        items = [p for p in pairs if p.label == label]
        if label in ("reworded", "unchanged") and not show_all:
            continue
        lines.append(f"{label.upper()}")
        if not items:
            lines.append("(none)")
            lines.append("")
            continue
        for k, p in enumerate(items, 1):
            if label == "changed":
                lines.append(f"{k}. [{p.reason}, sim {p.sim:.2f}]")
                lines.append(f"   old: {clause_text(p, 'old')}")
                lines.append(f"   new: {clause_text(p, 'new')}")
            elif label == "reworded":
                lines.append(f"{k}. [sim {p.sim:.2f}]")
                lines.append(f"   old: {clause_text(p, 'old')}")
                lines.append(f"   new: {clause_text(p, 'new')}")
            elif label == "unchanged":
                lines.append(f"{k}. {clause_text(p, 'old')}")
            else:  # added / removed
                text = clause_text(p, "new" if label == "added" else "old")
                lines.append(f"+ {text}" if label == "added" else f"- {text}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("old", nargs="?", help="path to the old version")
    ap.add_argument("new", nargs="?", help="path to the new version")
    ap.add_argument("--hard-cases", metavar="CSV",
                    help="evaluate a CSV of pairs (columns: old,new,expected) instead of a document pair")
    ap.add_argument("--model", default=MODEL_ID)
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help="similarity above which a pair is Reworded (default %(default)s)")
    ap.add_argument("--floor", type=float, default=DEFAULT_FLOOR,
                    help="similarity below which a clause is Added/Removed (default %(default)s)")
    ap.add_argument("--claim-words", metavar="A,B,C", default=None,
                    help="comma-separated risky phrases to check (default: built-in list)")
    ap.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS,
                    help="token budget per clause; the model reads 512 tokens "
                         "by default, up to 2,048 if you raise the limit "
                         "(default %(default)s)")
    ap.add_argument("--no-claim-check", action="store_true",
                    help="disable the claim-words check")
    ap.add_argument("--show-all", action="store_true", help="also print Unchanged and Reworded clauses")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    if not args.hard_cases and (not args.old or not args.new):
        ap.error("provide old and new file paths, or --hard-cases CSV")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(args.model, revision=MODEL_REVISION,
                                trust_remote_code=True)
    max_tokens = min(args.max_tokens, MAX_TOKEN_LIMIT)

    claim_words = [w.strip() for w in args.claim_words.split(",")] if args.claim_words else None
    claim_check = not args.no_claim_check

    if args.hard_cases:
        eval_hard_cases(args.hard_cases, model, args.threshold, args.floor,
                        claim_check, claim_words, max_tokens)
        return

    with open(args.old, encoding="utf-8") as f:
        old_text = f.read()
    with open(args.new, encoding="utf-8") as f:
        new_text = f.read()

    pairs = compare(old_text, new_text, model, args.threshold, args.floor,
                    max_tokens, claim_check, claim_words)
    if args.json:
        print(json.dumps([{
            "label": p.label, "old": p.old, "new": p.new,
            "sim": p.sim, "reason": p.reason,
        } for p in pairs], indent=2))
    else:
        print(render_report(pairs, args.old, args.new, args.model,
                            args.threshold, args.floor, args.show_all))


if __name__ == "__main__":
    main()
