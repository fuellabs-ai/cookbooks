#!/usr/bin/env python3
"""Sort from a handful.

Show it a few examples per label and it sorts the rest. Each new item is
scored against every label. If the top label wins by a clear margin over
the second, the item gets that label. If not, it goes to "needs a human"
instead of guessing, with the top 2 labels shown.

Embeddings only. No LLM, no fine-tuning, no training run, no API key.
It runs on CPU.

The model is HobbyLM-Embed 140M loaded through Sentence Transformers with
trust_remote_code=True. Text goes in as plain text, with no prompt_name:
classification embeds everything the same way. Vectors are unit-norm, so
a dot product is a cosine similarity.

Usage:
    python sort_handful.py items.csv --labels labels.yaml
    python sort_handful.py items.csv --labels labels.yaml --margin 0.05
    python sort_handful.py items.csv --labels labels.yaml --knn 3
    python sort_handful.py items.csv --labels labels.yaml --corrections fixed.csv

labels.yaml gives each label a handful of example texts, about 5 to start:

    bug:
      - "fit() crashes with a segmentation fault when n_jobs=-1"
      - "predict gives different results between two versions"
    question:
      - "How do I get the feature names out of a fitted pipeline?"
      ...

A label can carry "never_hide: true". Items whose top label has it are
labelled as usual but also flagged needs_human, because that label must
always reach a person.

Batch mode only, on a CSV. There is no watch mode. Output is sorted.csv
(text, label, score, margin, needs_human, plus the expected label from
the input when there is one) and report.html.

Corrections loop: move an item to the right label, put it in a CSV with
text and label columns, and pass it with --corrections. It is appended
as a new example, the centroids are rebuilt, and the run repeats. Copy
the correction into labels.yaml to keep it.

The margin is a setting. calibrate.py recommends one from your own
labelled items and saves it to margin.json next to labels.yaml. A fixed
margin does not carry over between models or item sets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Sequence

import numpy as np

DEFAULT_MODEL = "harims95/hobbylm-embed-140m"
MODEL_REVISION = "ea708cee"
DEFAULT_MARGIN = 0.05
DEFAULT_METHOD = "centroid"
DEFAULT_K = 5
NEEDS_HUMAN_LABEL = "needs a human"
CONFIG_NAME = "margin.json"
SORTED_NAME = "sorted.csv"
REPORT_NAME = "report.html"

RESULTS_COLUMNS = ["text", "label", "score", "margin", "needs_human"]
TEXT_COLUMNS = ["text", "message", "body", "issue"]
LABEL_COLUMNS = ["label", "expected", "true_label", "correct_label"]

# Unit-norm 512-dim vectors for this model, used for empty shapes.
EMBED_DIM = 512


@dataclass
class LabelDef:
    name: str
    examples: list[str]
    never_hide: bool = False


# Issue-template boilerplate that embedding does not need: markdown headings,
# template prompts, HTML comments, placeholder answers and checklist items.
# The list covers the scikit-learn issue templates; longest phrases first so
# that "describe the bug and give evidence..." is not cut at "describe the
# bug" and leaves its tail behind.
TEMPLATE_PROMPTS = [
    "describe the bug and give evidence about its user-facing impact",
    "describe the issue linked to the documentation",
    "describe the workflow you want to enable",
    "describe alternatives you've considered, if relevant",
    "suggest a potential alternative/fix",
    "steps/code to reproduce",
    "expected results",
    "actual results",
    "introduce yourself",
    "additional context",
    "describe the issue",
    "describe the bug",
    "versions",
    "no response",
]


def strip_issue_text(text: str) -> str:
    """Remove issue-template boilerplate, keep the title and the person's words.

    Built for plain text where line breaks were collapsed: it works on the
    flat string. It removes HTML comments, checklist items, GitHub alert
    markers, template prompt headings (with their # markers) and any
    remaining markdown heading markers. A blunt text rule: a # comment
    inside pasted code can lose its #, and a personal heading keeps its
    words without its marker.
    """
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # Checklist items run from one checkbox to the next in flat text.
    text = re.sub(r"- \[[ xX]\][^-]*?(?=- \[[ xX]\]|$)", " ", text)
    # The maintainer-workflow warning that issue templates paste in. It ends
    # with the words 'label.' after the triage link; if the body was
    # truncated inside the warning, everything after it is boilerplate.
    match = re.search(r"This issue is not yet ready for a PR\.", text, flags=re.IGNORECASE)
    if match:
        rest = text[match.start():]
        end = re.search(r"label\.\s*", rest)
        cut = match.start() + (end.end() if end else len(rest))
        text = text[:match.start()] + " " + text[cut:]
    # GitHub alert markers.
    text = re.sub(r">\s*\[!(?:WARNING|NOTE|Warning|Note|Caution|Important)\]", " ", text)
    # The template's placeholder answer.
    text = re.sub(r"_\s*no response\s*_", " ", text, flags=re.IGNORECASE)
    for phrase in TEMPLATE_PROMPTS:
        pattern = re.compile(
            r"(?:^|[\s>#*])"                      # start, heading or bold marker
            r"(?:#{1,6}\s*)?"                     # heading marker
            r"(?:\*\*)?"
            + re.escape(phrase)
            + r"(?:\*\*)?"
            r"(?=\s|$)",
            re.IGNORECASE,
        )
        text = pattern.sub(" ", text)
    # Remaining markdown heading markers.
    text = re.sub(r"(?:^|\s)#{1,6}(?=\s)", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


@dataclass
class Item:
    text: str
    expected: str = ""

    @property
    def short(self) -> str:
        flat = " ".join(self.text.split())
        return flat[:120] + "..." if len(flat) > 120 else flat


@dataclass
class Result:
    item: Item
    label: str
    score: float
    margin: float
    needs_human: bool
    second_label: str
    second_score: float


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------


def load_labels(path: str | Path) -> list[LabelDef]:
    """Read labels.yaml: a mapping of label name to a list of example texts."""
    import yaml

    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError(f"{path}: expected a mapping of label name to examples")
    labels: list[LabelDef] = []
    for name, value in data.items():
        name = str(name).strip().lower()
        if isinstance(value, dict):
            examples = value.get("examples") or []
            never_hide = bool(value.get("never_hide", False))
        else:
            examples = value or []
            never_hide = False
        examples = [str(example).strip() for example in examples if str(example).strip()]
        labels.append(LabelDef(name=name, examples=examples, never_hide=never_hide))
    names = [label.name for label in labels]
    if len(names) != len(set(names)):
        raise ValueError(f"{path}: duplicate label names in {names}")
    return labels


def sample_examples_from_csv(
    items: Sequence[Item], labels: Sequence[LabelDef], per_label: int, seed: int
) -> list[tuple[str, str]]:
    """Sample up to per_label examples per label from a labelled CSV.

    Used for a real handful: the examples come from items that are held out
    of the test set. The sampling is fixed by the seed.
    """
    rng = random.Random(seed)
    by_label: dict[str, list[int]] = {}
    for position, item in enumerate(items):
        by_label.setdefault(item.expected, []).append(position)
    pool: list[tuple[str, str]] = []
    for label in labels:
        positions = by_label.get(label.name, [])
        take = min(per_label, len(positions))
        picked = rng.sample(positions, take) if take else []
        pool.extend((items[position].text, label.name) for position in picked)
    return pool


def build_example_pool(
    labels: Sequence[LabelDef],
    corrections: Sequence[tuple[str, str]],
    examples_from: Sequence[Item] | None = None,
    per_label: int = 0,
    seed: int = 7,
) -> list[tuple[str, str]]:
    """The handful of examples per label, with corrections appended at the end.

    With examples_from and per_label > 0, the examples are sampled from that
    labelled CSV instead of the texts in labels.yaml.
    """
    if examples_from is not None and per_label > 0:
        pool = sample_examples_from_csv(examples_from, labels, per_label, seed)
    else:
        pool = [(example, label.name) for label in labels for example in label.examples]
    pool.extend(corrections)
    return pool


def load_items(path: str | Path) -> list[Item]:
    """Read items from a CSV with a text column and an optional label column."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"No rows in {path}")

    columns = {key.strip().lower(): key for key in rows[0] if key is not None}
    text_column = next((columns[name] for name in TEXT_COLUMNS if name in columns), None)
    if text_column is None:
        text_column = list(rows[0])[0]
    label_column = next((columns[name] for name in LABEL_COLUMNS if name in columns), None)

    items = []
    for row in rows:
        text = (row.get(text_column) or "").strip()
        if not text:
            continue
        expected = (row.get(label_column) or "").strip().lower() if label_column else ""
        items.append(Item(text=text, expected=expected))
    if not items:
        raise ValueError(f"No items found in {path}")
    return items


def load_corrections(path: str | Path) -> list[tuple[str, str]]:
    """Read moved items from a CSV with text and label columns."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    corrections = []
    for row in rows:
        cleaned = {key.strip().lower(): (value or "").strip() for key, value in row.items()}
        text = cleaned.get("text", "")
        label = cleaned.get("label", "")
        if text and label:
            corrections.append((text, label.lower()))
    if not corrections:
        raise ValueError(f"{path}: needs text and label columns with values")
    return corrections


# ---------------------------------------------------------------------------
# embeddings
# ---------------------------------------------------------------------------


def load_model(model_name: str = DEFAULT_MODEL):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, revision=MODEL_REVISION,
                               trust_remote_code=True)


def _batch_key(model_name: str, texts: Sequence[str]) -> str:
    digest = hashlib.sha256()
    digest.update(model_name.encode("utf-8"))
    digest.update(b"\0")
    for text in texts:
        digest.update(text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:20]


def embed_texts(
    texts: Sequence[str],
    model,
    model_name: str = DEFAULT_MODEL,
    cache_dir: str | Path | None = None,
    rebuild_cache: bool = False,
) -> np.ndarray:
    """Embed plain text as unit-norm vectors, reusing a per-batch cache."""
    if not texts:
        return np.zeros((0, EMBED_DIM), dtype=np.float32)

    cache_path = None
    if cache_dir is not None:
        cache_dir = Path(cache_dir).expanduser().resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{_batch_key(model_name, texts)}.npz"

    if cache_path is not None and cache_path.exists() and not rebuild_cache:
        saved = np.load(cache_path)
        vectors = saved["vectors"]
        if vectors.shape[0] == len(texts):
            return np.asarray(vectors, dtype=np.float32)

    vectors = model.encode(
        list(texts),
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    vectors = np.asarray(vectors, dtype=np.float32)
    # Unit-norm on purpose: dot products then behave as cosine similarity.
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    vectors = vectors / norms

    if cache_path is not None:
        np.savez_compressed(cache_path, vectors=vectors)
    return vectors


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


def score_matrix(
    items: Sequence[Item],
    example_pool: Sequence[tuple[str, str]],
    model,
    labels: Sequence[LabelDef],
    model_name: str = DEFAULT_MODEL,
    method: str = DEFAULT_METHOD,
    k: int = DEFAULT_K,
    cache_dir: str | Path | None = None,
    rebuild_cache: bool = False,
) -> tuple[np.ndarray, list[str], set[str]]:
    """Score every item against every label. Returns the score matrix.

    With method="centroid" each label is the unit-norm mean of its example
    vectors, and the score is the cosine to it. With method="knn" the score
    is the mean cosine to the k nearest example vectors of each label: a
    nearest-neighbour vote instead of a centroid.
    """
    label_names = [label.name for label in labels]
    never_hide = {label.name for label in labels if label.never_hide}

    item_vectors = embed_texts(
        [item.text for item in items], model, model_name=model_name,
        cache_dir=cache_dir, rebuild_cache=rebuild_cache,
    )
    example_vectors = embed_texts(
        [text for text, _ in example_pool], model, model_name=model_name,
        cache_dir=cache_dir, rebuild_cache=rebuild_cache,
    )

    if method == "knn":
        # Mean similarity to the k nearest examples of each label.
        similarities = item_vectors @ example_vectors.T
        label_of_example = np.array([name for _, name in example_pool])
        scores = np.zeros((len(items), len(label_names)), dtype=np.float32)
        for column, name in enumerate(label_names):
            mask = label_of_example == name
            if not mask.any():
                continue
            per_label = similarities[:, mask]
            kk = min(k, per_label.shape[1])
            top = np.sort(per_label, axis=1)[:, -kk:]
            scores[:, column] = top.mean(axis=1)
    elif method == "centroid":
        # Nearest-centroid.
        scores = np.zeros((len(items), len(label_names)), dtype=np.float32)
        for column, name in enumerate(label_names):
            mask = np.array([pool_label == name for _, pool_label in example_pool])
            centroid = example_vectors[mask].mean(axis=0)
            centroid /= np.linalg.norm(centroid)
            scores[:, column] = item_vectors @ centroid
    else:
        raise ValueError(f"unknown method: {method} (use centroid or knn)")

    return scores, label_names, never_hide


def score_items(
    items: Sequence[Item],
    example_pool: Sequence[tuple[str, str]],
    model,
    labels: Sequence[LabelDef],
    model_name: str = DEFAULT_MODEL,
    margin: float = DEFAULT_MARGIN,
    method: str = DEFAULT_METHOD,
    k: int = DEFAULT_K,
    cache_dir: str | Path | None = None,
    rebuild_cache: bool = False,
) -> list[Result]:
    """Turn the score matrix into labelled results under the given margin."""
    scores, label_names, never_hide = score_matrix(
        items, example_pool, model, labels,
        model_name=model_name, method=method, k=k,
        cache_dir=cache_dir, rebuild_cache=rebuild_cache,
    )

    results = []
    for position, item in enumerate(items):
        row = scores[position]
        order = np.argsort(-row)
        top = int(order[0])
        second = int(order[1]) if len(order) > 1 else top
        top_score = float(row[top])
        top_name = label_names[top]
        item_margin = top_score - float(row[second])
        human = item_margin < margin or top_name in never_hide
        results.append(
            Result(
                item=item,
                label=top_name,
                score=top_score,
                margin=item_margin,
                needs_human=human,
                second_label=label_names[second],
                second_score=float(row[second]),
            )
        )
    return results


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def load_saved_config(labels_path: str | Path) -> dict:
    """Read the settings that calibrate.py saved, if there are any."""
    path = Path(labels_path).expanduser().resolve().parent / CONFIG_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


# ---------------------------------------------------------------------------
# outputs
# ---------------------------------------------------------------------------


def write_sorted_csv(results: Sequence[Result], out_path: Path) -> None:
    columns = list(RESULTS_COLUMNS)
    if results and results[0].item.expected:
        columns.append("expected")
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for result in results:
            writer.writerow(
                [
                    result.item.text,
                    result.label,
                    f"{result.score:.3f}",
                    f"{result.margin:.3f}",
                    result.needs_human,
                    result.item.expected,
                ][: len(columns)]
            )


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    parts = ["<table>", "<tr>" + "".join(f"<th>{escape(h)}</th>" for h in headers) + "</tr>"]
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>")
    parts.append("</table>")
    return "\n".join(parts)


def write_report(
    results: Sequence[Result],
    out_path: Path,
    margin: float,
    method: str,
    k: int,
    model_name: str,
) -> None:
    expected_known = bool(results and results[0].item.expected)
    wrongly_sorted = [
        result for result in results
        if result.item.expected and not result.needs_human and result.label != result.item.expected
    ]
    human_queue = [result for result in results if result.needs_human]

    if expected_known:
        summary_sentence = (
            f"<p>{len(human_queue)} items went to a person instead of guessing. "
            f"{len(wrongly_sorted)} items were labelled differently from their "
            "expected label.</p>"
        )
    else:
        summary_sentence = (
            f"<p>{len(human_queue)} items went to a person instead of guessing.</p>"
        )
    lines = [
        "<!doctype html>",
        '<html><head><meta charset="utf-8">',
        "<title>Sort from a handful: report</title>",
        "<style>",
        "body{font-family:-apple-system,Segoe UI,Helvetica,sans-serif;margin:2rem;max-width:60rem;}",
        "table{border-collapse:collapse;width:100%;margin:1rem 0;}",
        "th,td{border:1px solid #ccc;padding:.35rem .6rem;text-align:left;vertical-align:top;}",
        "th{background:#f2f2f2;} td.num{text-align:right;}",
        "h2{margin-top:2rem;}",
        "</style></head><body>",
        "<h1>Sort from a handful: report</h1>",
        f"<p>{len(results)} items. Margin {margin:.3f}. "
        + (f"nearest-neighbour vote, k={k}. " if method == "knn" else "Nearest-centroid. ")
        + f"Model {escape(model_name)}.</p>",
        summary_sentence,
    ]

    # Per-label summary.
    per_label: dict[str, dict[str, int]] = {}
    for result in results:
        row = per_label.setdefault(result.label, {"sorted": 0, "human": 0, "wrong": 0})
        if result.needs_human:
            row["human"] += 1
        else:
            row["sorted"] += 1
            if expected_known and result.item.expected and result.label != result.item.expected:
                row["wrong"] += 1
    label_rows = []
    for name in sorted(per_label):
        row = per_label[name]
        wrong = f"{row['wrong']}" if expected_known else "-"
        label_rows.append([name, row["sorted"], row["human"], wrong])
    lines.append("<h2>Per label</h2>")
    lines.append(_table(["label", "sorted", "sent to a person", "wrongly sorted"], label_rows))

    lines.append("<h2>Needs a human</h2>")
    lines.append(_table(
        ["top label", "score", "second label", "second score", "margin", "text"],
        [
            [
                result.label, f"{result.score:.3f}", result.second_label,
                f"{result.second_score:.3f}", f"{result.margin:.3f}", result.item.short,
            ]
            for result in human_queue
        ],
    ))

    if expected_known:
        lines.append("<h2>Wrongly sorted</h2>")
        lines.append(_table(
            ["expected", "got", "score", "margin", "text"],
            [
                [
                    result.item.expected, result.label, f"{result.score:.3f}",
                    f"{result.margin:.3f}", result.item.short,
                ]
                for result in wrongly_sorted
            ],
        ))

    lines.append("</body></html>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def print_summary(results: Sequence[Result], margin: float, method: str, k: int) -> None:
    expected_known = bool(results and results[0].item.expected)
    human_queue = [result for result in results if result.needs_human]
    wrongly_sorted = [
        result for result in results
        if result.item.expected and not result.needs_human and result.label != result.item.expected
    ]
    mode = f"nearest-neighbour vote k={k}" if method == "knn" else "nearest-centroid"
    print(f"items: {len(results)}  margin: {margin:.3f}  method: {mode}")
    print(f"sorted: {len(results) - len(human_queue)}  sent to a person: {len(human_queue)}")
    if expected_known:
        print(f"wrongly sorted: {len(wrongly_sorted)}")
        for result in wrongly_sorted:
            print(
                f"  {result.item.short} -> {result.label} (expected {result.item.expected}, "
                f"score {result.score:.3f}, margin {result.margin:.3f})"
            )
    print("sent to a person:")
    for result in human_queue:
        print(
            f"  {result.item.short} -> {result.label} or {result.second_label} "
            f"(margin {result.margin:.3f})"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sort a CSV of items from a handful of examples per label."
    )
    parser.add_argument("items", type=Path, help="CSV with a text column, and an optional label column")
    parser.add_argument("--labels", type=Path, required=True, help="labels.yaml naming the labels (and their never_hide flags); its example texts are used unless --examples-from is given")
    parser.add_argument(
        "--margin", type=float, default=None,
        help=f"Margin the top label needs over the second (default: margin.json if present, else {DEFAULT_MARGIN})",
    )
    parser.add_argument(
        "--method", choices=["centroid", "knn"], default=None,
        help="Score against a centroid per label, or by nearest-neighbour vote (default: the method in margin.json, else %(default)s)",
    )
    parser.add_argument(
        "--k", type=int, default=None,
        help="Neighbours per label for --method knn (default: the k in margin.json, else %(default)s)",
    )
    parser.add_argument(
        "--examples-from", type=Path, default=None,
        help="Labelled CSV to draw the handful of examples per label from, instead of the texts in labels.yaml",
    )
    parser.add_argument(
        "--per-label", type=int, default=0,
        help="Examples per label to sample from --examples-from (0: use labels.yaml)",
    )
    parser.add_argument(
        "--seed", type=int, default=7, help="Seed for sampling the examples (default: 7)"
    )
    parser.add_argument(
        "--strip-templates", action="store_true",
        help="Strip issue-template boilerplate (headings, prompts, comments, checklists) before embedding",
    )
    parser.add_argument("--corrections", type=Path, default=None, help="CSV of moved items (text,label) to append as examples")
    parser.add_argument("--out-dir", type=Path, default=None, help="Where to write sorted.csv and report.html (default: next to the items CSV)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Sentence Transformers model")
    parser.add_argument("--cache-dir", default=None, help="Embedding cache folder (default: next to labels.yaml)")
    parser.add_argument(
        "--rebuild-cache", action="store_true", help="Ignore and replace the embedding cache"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    saved = load_saved_config(args.labels)
    margin = args.margin
    if margin is None:
        saved_margin = saved.get("margin")
        margin = saved_margin if isinstance(saved_margin, (int, float)) else DEFAULT_MARGIN
    method = args.method if args.method is not None else saved.get("method", DEFAULT_METHOD)
    if method not in ("centroid", "knn"):
        method = DEFAULT_METHOD
    k = args.k if args.k is not None else saved.get("k", DEFAULT_K)
    if method == "knn" and (not isinstance(k, int) or k < 1):
        k = DEFAULT_K

    if args.per_label > 0 and args.examples_from is None:
        parser.error("--per-label needs --examples-from")

    labels = load_labels(args.labels)
    items = load_items(args.items)
    if args.strip_templates:
        for item in items:
            item.text = strip_issue_text(item.text)
    corrections = load_corrections(args.corrections) if args.corrections else []
    if args.strip_templates:
        corrections = [(strip_issue_text(text), label) for text, label in corrections]
    if corrections:
        print(f"appending {len(corrections)} corrections as new examples")

    examples_source = None
    if args.examples_from is not None:
        examples_source = load_items(args.examples_from)
        unlabelled = [item for item in examples_source if not item.expected]
        if unlabelled:
            raise ValueError(
                f"{args.examples_from}: {len(unlabelled)} items have no label; "
                "the example CSV needs a label column"
            )
        if args.strip_templates:
            for item in examples_source:
                item.text = strip_issue_text(item.text)
        known = {label.name for label in labels}
        unknown = sorted({item.expected for item in examples_source} - known)
        if unknown:
            raise ValueError(
                f"{args.examples_from}: labels {unknown} are not in labels.yaml "
                f"({sorted(known)})."
            )

    cache_dir = args.cache_dir if args.cache_dir is not None else args.labels.parent / ".hobbylm_cache"
    model = load_model(args.model)
    example_pool = build_example_pool(
        labels, corrections,
        examples_from=examples_source, per_label=args.per_label, seed=args.seed,
    )
    if args.per_label > 0 and args.examples_from is not None:
        print(f"examples: {args.per_label} per label sampled from {args.examples_from} (seed {args.seed})")
    results = score_items(
        items,
        example_pool,
        model,
        labels,
        model_name=args.model,
        margin=margin,
        method=method,
        k=k,
        cache_dir=cache_dir,
        rebuild_cache=args.rebuild_cache,
    )

    out_dir = args.out_dir if args.out_dir is not None else args.items.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    write_sorted_csv(results, out_dir / SORTED_NAME)
    write_report(results, out_dir / REPORT_NAME, margin, method, k, args.model)
    print(f"wrote {out_dir / SORTED_NAME}")
    print(f"wrote {out_dir / REPORT_NAME}")
    print()
    print_summary(results, margin, method, k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
