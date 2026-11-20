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
import sys
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Sequence

import numpy as np

DEFAULT_MODEL = "harims95/hobbylm-embed-140m"
DEFAULT_MARGIN = 0.05
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
        if not examples:
            raise ValueError(f"{path}: label '{name}' has no example texts")
        labels.append(LabelDef(name=name, examples=examples, never_hide=never_hide))
    names = [label.name for label in labels]
    if len(names) != len(set(names)):
        raise ValueError(f"{path}: duplicate label names in {names}")
    return labels


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

    return SentenceTransformer(model_name, trust_remote_code=True)


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


def build_example_pool(labels: Sequence[LabelDef], corrections: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """The handful of examples per label, with corrections appended at the end."""
    pool = [(example, label.name) for label in labels for example in label.examples]
    pool.extend(corrections)
    return pool


def score_matrix(
    items: Sequence[Item],
    example_pool: Sequence[tuple[str, str]],
    model,
    labels: Sequence[LabelDef],
    model_name: str = DEFAULT_MODEL,
    knn: int = 0,
    cache_dir: str | Path | None = None,
    rebuild_cache: bool = False,
) -> tuple[np.ndarray, list[str], set[str]]:
    """Score every item against every label. Returns the score matrix.

    Default is nearest-centroid: each label is the unit-norm mean of its
    example vectors, and the score is the cosine to it. With knn > 0 the
    score is the mean cosine to the k nearest example vectors of each
    label instead.
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

    if knn > 0:
        # Mean similarity to the k nearest examples of each label.
        similarities = item_vectors @ example_vectors.T
        label_of_example = np.array([name for _, name in example_pool])
        scores = np.zeros((len(items), len(label_names)), dtype=np.float32)
        for column, name in enumerate(label_names):
            mask = label_of_example == name
            if not mask.any():
                continue
            per_label = similarities[:, mask]
            k = min(knn, per_label.shape[1])
            top = np.sort(per_label, axis=1)[:, -k:]
            scores[:, column] = top.mean(axis=1)
    else:
        # Nearest-centroid.
        scores = np.zeros((len(items), len(label_names)), dtype=np.float32)
        for column, name in enumerate(label_names):
            mask = np.array([pool_label == name for _, pool_label in example_pool])
            centroid = example_vectors[mask].mean(axis=0)
            centroid /= np.linalg.norm(centroid)
            scores[:, column] = item_vectors @ centroid

    return scores, label_names, never_hide


def score_items(
    items: Sequence[Item],
    example_pool: Sequence[tuple[str, str]],
    model,
    labels: Sequence[LabelDef],
    model_name: str = DEFAULT_MODEL,
    margin: float = DEFAULT_MARGIN,
    knn: int = 0,
    cache_dir: str | Path | None = None,
    rebuild_cache: bool = False,
) -> list[Result]:
    """Turn the score matrix into labelled results under the given margin."""
    scores, label_names, never_hide = score_matrix(
        items, example_pool, model, labels,
        model_name=model_name, knn=knn,
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


def load_saved_margin(labels_path: str | Path) -> float | None:
    """Read the margin that calibrate.py saved, if there is one."""
    path = Path(labels_path).expanduser().resolve().parent / CONFIG_NAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    value = data.get("margin")
    if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0:
        return float(value)
    return None


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
    knn: int,
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
        + (f"k-NN k={knn}. " if knn else "Nearest-centroid. ")
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


def print_summary(results: Sequence[Result], margin: float, knn: int) -> None:
    expected_known = bool(results and results[0].item.expected)
    human_queue = [result for result in results if result.needs_human]
    wrongly_sorted = [
        result for result in results
        if result.item.expected and not result.needs_human and result.label != result.item.expected
    ]
    mode = f"k-NN k={knn}" if knn else "nearest-centroid"
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
    parser.add_argument("--labels", type=Path, required=True, help="labels.yaml with a handful of examples per label")
    parser.add_argument(
        "--margin", type=float, default=None,
        help=f"Margin the top label needs over the second (default: margin.json if present, else {DEFAULT_MARGIN})",
    )
    parser.add_argument("--knn", type=int, default=0, help="Use k-NN with k examples per label instead of centroids")
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

    margin = args.margin
    if margin is None:
        margin = load_saved_margin(args.labels)
    if margin is None:
        margin = DEFAULT_MARGIN

    labels = load_labels(args.labels)
    items = load_items(args.items)
    corrections = load_corrections(args.corrections) if args.corrections else []
    if corrections:
        print(f"appending {len(corrections)} corrections as new examples")

    cache_dir = args.cache_dir if args.cache_dir is not None else args.labels.parent / ".hobbylm_cache"
    model = load_model(args.model)
    example_pool = build_example_pool(labels, corrections)
    results = score_items(
        items,
        example_pool,
        model,
        labels,
        model_name=args.model,
        margin=margin,
        knn=args.knn,
        cache_dir=cache_dir,
        rebuild_cache=args.rebuild_cache,
    )

    out_dir = args.out_dir if args.out_dir is not None else args.items.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    write_sorted_csv(results, out_dir / SORTED_NAME)
    write_report(results, out_dir / REPORT_NAME, margin, args.knn, args.model)
    print(f"wrote {out_dir / SORTED_NAME}")
    print(f"wrote {out_dir / REPORT_NAME}")
    print()
    print_summary(results, margin, args.knn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
