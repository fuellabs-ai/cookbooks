#!/usr/bin/env python3
"""Try a few group-size and similarity settings on a labelled sample.

Each example folder has a labelled_sample.csv with 50 hand-labelled rows
(text, group, dup_id). group is the true topic of the row. dup_id is a shared
id for rows that are wordings of one near-identical ask, and is scored
separately: it is fine for those rows to land in a said-again cluster or in
their topic group, so the group match ignores it.

This script runs the piles.py pipeline on each sample at several settings and
prints how well the predicted grouping matches the hand labels, measured with
the adjusted Rand index (1.0 is a perfect match, 0.0 is chance) and pairwise
purity.

Usage:
    python calibrate.py examples/feature_requests/labelled_sample.csv
    python calibrate.py examples
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
from sklearn.metrics import adjusted_rand_score

from piles import (
    DEFAULT_CLUSTER_SIM,
    DEFAULT_DEDUP_SIM,
    DEFAULT_MIN_GROUP,
    embed,
    load_model,
    segment,
)

DEDUP_GRID = [0.82, 0.86, 0.90, 0.94]
CLUSTER_GRID = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
MIN_GROUP_GRID = [2, 3, 5]


def load_sample(path: Path) -> tuple[list[str], list[str], list[str]]:
    texts: list[str] = []
    groups: list[str] = []
    dups: list[str] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            texts.append(row["text"])
            groups.append(row["group"])
            dups.append(row.get("dup_id") or "")
    return texts, groups, dups


def predicted_partition(vectors: np.ndarray, dedup_sim: float, cluster_sim: float, min_group: int) -> list[str]:
    """One partition label per request, what the report would show."""
    result = segment(
        vectors, dedup_sim=dedup_sim, cluster_sim=cluster_sim, min_group=min_group
    )
    labels: list[str] = [""] * vectors.shape[0]
    for number, cluster in enumerate(result["said_again"]):
        for index in cluster["members"]:
            labels[index] = f"again#{number}"
    for index, cluster_id in result["cluster_of"].items():
        labels[index] = f"group#{cluster_id}"
    for index, cluster_id in result["small_of"].items():
        labels[index] = f"small#{cluster_id}"
    for index in result["doesn_fit"]:
        if labels[index] == "":
            labels[index] = "alone"
    assert all(labels), "every request needs a partition label"
    return labels


def said_again_quality(
    texts: list[str],
    dups: list[str],
    vectors: np.ndarray,
    dedup_sim: float,
    cluster_sim: float,
    min_group: int,
) -> tuple[float, float]:
    """Recall and purity of said-again capture, against dup_id.

    Recall: share of same-dup_id pairs that end up in the same said-again
    cluster. Purity: share of same-cluster pairs that share a dup_id.
    """
    result = segment(
        vectors, dedup_sim=dedup_sim, cluster_sim=cluster_sim, min_group=min_group
    )
    cluster_index: dict[int, int] = {}
    for number, cluster in enumerate(result["said_again"]):
        for index in cluster["members"]:
            cluster_index[index] = number
    dup_pairs = 0
    captured = 0
    cluster_pairs = 0
    good_pairs = 0
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if dups[i] and dups[i] == dups[j]:
                dup_pairs += 1
                if cluster_index.get(i) is not None and cluster_index.get(i) == cluster_index.get(j):
                    captured += 1
            if cluster_index.get(i) is not None and cluster_index.get(i) == cluster_index.get(j):
                cluster_pairs += 1
                if dups[i] and dups[i] == dups[j]:
                    good_pairs += 1
    recall = captured / dup_pairs if dup_pairs else 1.0
    purity = good_pairs / cluster_pairs if cluster_pairs else 1.0
    return recall, purity


def pairwise_purity(true_labels: Sequence[str], pred_labels: Sequence[str]) -> float:
    """Share of same-prediction pairs that also share a true label."""
    same_pairs = 0
    good_pairs = 0
    n = len(pred_labels)
    for i in range(n):
        for j in range(i + 1, n):
            if pred_labels[i] == pred_labels[j]:
                same_pairs += 1
                if true_labels[i] == true_labels[j]:
                    good_pairs += 1
    return good_pairs / same_pairs if same_pairs else 1.0


def score_combo(
    vectors: np.ndarray, true_labels: list[str], dedup_sim: float, cluster_sim: float, min_group: int
) -> tuple[float, float, int]:
    pred = predicted_partition(vectors, dedup_sim, cluster_sim, min_group)
    ari = adjusted_rand_score(true_labels, pred)
    purity = pairwise_purity(true_labels, pred)
    return ari, purity, len(set(pred))


def print_matrix(
    title: str, vectors: np.ndarray, true_labels: list[str], min_group: int
) -> list[tuple[float, float, int, float, float, int]]:
    """Print one ARI matrix for a fixed min_group, return the scored combos."""
    rows: list[tuple[float, float, int, float, float, int]] = []
    header = "cluster_sim " + " ".join(f"{value:>6.2f}" for value in CLUSTER_GRID)
    print(f"  {title}")
    print(f"  {header}")
    for dedup_sim in DEDUP_GRID:
        cells = []
        for cluster_sim in CLUSTER_GRID:
            ari, purity, count = score_combo(vectors, true_labels, dedup_sim, cluster_sim, min_group)
            rows.append((dedup_sim, cluster_sim, min_group, ari, purity, count))
            cells.append(f"{ari:>6.2f}")
        print(f"  dedup {dedup_sim:.2f}   " + " ".join(cells))
    return rows


def run_sample(path: Path, model) -> tuple[list[dict], dict]:
    texts, groups, dups = load_sample(path)
    true_labels = list(groups)
    print(f"=== {path.parent.name} ({len(texts)} labelled requests, {len(set(true_labels))} true groups) ===")
    vectors = embed(texts, model)
    all_rows: list[tuple[float, float, int, float, float, int]] = []
    for min_group in MIN_GROUP_GRID:
        all_rows.extend(print_matrix(f"min_group {min_group}", vectors, true_labels, min_group))
    suggested = max(all_rows, key=lambda row: (row[3], row[4], -row[2]))
    s_dedup, s_cluster, s_min, s_ari, s_purity, s_count = suggested
    recall, sa_purity = said_again_quality(
        texts, dups, vectors, s_dedup, s_cluster, s_min
    )
    print(
        f"  suggested: dedup_sim {s_dedup}, cluster_sim {s_cluster}, "
        f"min_group {s_min}  ARI {s_ari:.3f}, purity {s_purity:.3f}, "
        f"{s_count} predicted groups; said-again recall {recall:.2f}, "
        f"purity {sa_purity:.2f}"
    )
    print()
    return all_rows, {"best": suggested, "name": path.parent.name}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sweep grouping settings on labelled samples.")
    parser.add_argument(
        "samples",
        nargs="*",
        default=["examples"],
        help="labelled_sample.csv files, or folders or a parent folder containing them",
    )
    args = parser.parse_args(argv)

    paths: list[Path] = []
    for raw in args.samples:
        path = Path(raw)
        if path.is_dir():
            paths.extend(sorted(path.glob("*/labelled_sample.csv")))
            if not paths:
                paths.extend(sorted(path.glob("labelled_sample.csv")))
        elif path.name == "labelled_sample.csv":
            paths.append(path)
        else:
            raise FileNotFoundError(f"No labelled_sample.csv at {path}")
    if not paths:
        print("No labelled samples found.", file=sys.stderr)
        return 1

    model = load_model()
    per_sample: dict[str, list[tuple[float, float, int, float, float, int]]] = {}
    bests: dict[str, tuple] = {}
    for path in paths:
        rows, info = run_sample(path, model)
        per_sample[path.parent.name] = rows
        bests[path.parent.name] = info["best"]

    # aggregate: mean ARI per combo across samples
    by_combo: dict[tuple, list[float]] = {}
    for rows in per_sample.values():
        for dedup_sim, cluster_sim, min_group, ari, _purity, _count in rows:
            by_combo.setdefault((dedup_sim, cluster_sim, min_group), []).append(ari)
    print("=== mean adjusted Rand index across examples ===")
    print(
        "(min_group moves small groups into the Doesn't fit bucket without "
        "changing how they match labels, so its rows repeat.)"
    )
    print("min_group  dedup_sim  " + " ".join(f"{v:>6.2f}" for v in CLUSTER_GRID))
    for min_group in MIN_GROUP_GRID:
        for dedup_sim in DEDUP_GRID:
            cells = [
                np.mean(by_combo[(dedup_sim, cluster_sim, min_group)])
                for cluster_sim in CLUSTER_GRID
            ]
            print(
                f"{min_group:>7}   {dedup_sim:>7.2f}   "
                + " ".join(f"{value:>6.2f}" for value in cells)
            )
    mean_rows = [
        (dedup_sim, cluster_sim, min_group, float(np.mean(aris)))
        for (dedup_sim, cluster_sim, min_group), aris in by_combo.items()
    ]
    overall = max(mean_rows, key=lambda row: (row[3], -row[2]))
    print(
        f"\nsuggested overall: dedup_sim {overall[0]}, cluster_sim {overall[1]}, "
        f"min_group {overall[2]} (mean ARI {overall[3]:.3f})"
    )
    print(
        f"defaults in piles.py: dedup_sim {DEFAULT_DEDUP_SIM}, "
        f"cluster_sim {DEFAULT_CLUSTER_SIM}, min_group {DEFAULT_MIN_GROUP}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
