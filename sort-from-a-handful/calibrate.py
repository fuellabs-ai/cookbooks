#!/usr/bin/env python3
"""Tune the margin for sort_handful.py on your own labelled items.

Input is an example folder with a labels.yaml and a CSV of labelled items
(items.csv or inbox.csv). Write the items once and do not reword them
after measuring. The script scores every item, sweeps margins, prints
wrongly-sorted versus sent-to-human at each step, recommends a margin,
and saves it to margin.json next to labels.yaml.

The margin is the gap the top label needs over the second label for the
item to be labelled instead of sent to a human. A low margin labels too
much, including the things it should not. A high margin sends too much
to a person. The sweep shows that trade-off on your items.

The recommendation rule: take the smallest margin at which wrongly-sorted
items are at most one in ten of the labelled items, counting only
margins with at least ten labelled items. If no margin in the sweep
manages that, the script says so and recommends the margin with the
lowest wrongly-sorted rate instead. Wrong labels are the failure mode;
a human check is a cost, not a mistake.

The script also sorts with 5, 10 and 25 examples per label sampled from
the labelled CSV, to show what a bigger handful buys. The sampled
examples are removed from the test set for that run, so every number is
measured on items that were not used as examples. A count that the CSV
cannot cover is skipped with a note.

Usage:
    python calibrate.py examples
    python calibrate.py examples/github_issues examples/careers_inbox
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from sort_handful import (
    CONFIG_NAME,
    DEFAULT_MODEL,
    Item,
    LabelDef,
    build_example_pool,
    load_labels,
    load_items,
    load_model,
    score_matrix,
)

ITEM_FILES = ["items.csv", "inbox.csv", "test.csv"]
TOLERANCE = 0.10  # at most one wrongly-sorted item in ten labelled items
MIN_LABELLED = 10


@dataclass
class Scored:
    labels: list[LabelDef]
    items: list[Item]
    scores: np.ndarray
    label_names: list[str]
    never_hide: set[str]

    @property
    def margins(self) -> np.ndarray:
        """Top score minus second score for every item."""
        values = []
        for row in self.scores:
            ordered = sorted(row)
            values.append(ordered[-1] - ordered[-2])
        return np.array(values)

    def top_names(self) -> list[str]:
        return [self.label_names[int(np.argmax(row))] for row in self.scores]


def load_scored(folder: Path, model, model_name: str, knn: int, cache_dir: Path) -> tuple[Scored, str]:
    labels = load_labels(folder / "labels.yaml")
    items_path = next(
        (folder / name for name in ITEM_FILES if (folder / name).exists()), None
    )
    if items_path is None:
        raise FileNotFoundError(
            f"{folder}: needs labels.yaml and one of {', '.join(ITEM_FILES)}"
        )
    items = load_items(items_path)
    unlabelled = [item for item in items if not item.expected]
    if unlabelled:
        raise ValueError(
            f"{items_path}: {len(unlabelled)} items have no label. Every item in a "
            "calibration CSV needs a label."
        )
    known = {label.name for label in labels}
    unknown = sorted({item.expected for item in items} - known)
    if unknown:
        raise ValueError(
            f"{items_path}: labels {unknown} are not in labels.yaml "
            f"({sorted(known)}). The CSV and labels.yaml must use the same names."
        )
    pool = build_example_pool(labels, [])
    scores, label_names, never_hide = score_matrix(
        items, pool, model, labels,
        model_name=model_name, knn=knn, cache_dir=cache_dir,
    )
    return Scored(
        labels=labels, items=items, scores=scores,
        label_names=label_names, never_hide=never_hide,
    ), items_path.name


def metrics(scored: Scored, margin: float) -> tuple[int, int, int]:
    """Count labelled, wrongly-sorted and sent-to-human items at one margin.

    Sent-to-human is everything flagged for a person: the unsure items and
    the never_hide labels. Wrongly-sorted is everything labelled with the
    wrong label. Both kinds end up in front of a person eventually, but a
    wrongly-sorted item carries a wrong label, which is the failure mode.
    """
    margins = scored.margins
    top = scored.top_names()
    labelled = 0
    wrongly_sorted = 0
    sent_to_human = 0
    for position, item in enumerate(scored.items):
        if margins[position] < margin or top[position] in scored.never_hide:
            sent_to_human += 1
        else:
            labelled += 1
            if top[position] != item.expected:
                wrongly_sorted += 1
    return labelled, wrongly_sorted, sent_to_human


def recommend_margin(scored: Scored, start: float, stop: float, resolution: float) -> tuple[float, bool]:
    """Pick the margin, or fall back and report that no margin managed it.

    Returns (margin, met_tolerance). The rule: the smallest margin where
    wrongly-sorted items are at most one in ten of the labelled items,
    counting only margins with at least ten labelled items. If no margin
    manages that, the margin with the lowest wrongly-sorted rate among
    margins with at least ten labelled items.
    """
    best: tuple[float, float] | None = None  # (rate, margin)
    for step in range(round((stop - start) / resolution) + 1):
        margin = round(start + step * resolution, 3)
        labelled, wrongly_sorted, _ = metrics(scored, margin)
        if labelled < MIN_LABELLED:
            continue
        rate = wrongly_sorted / labelled
        if rate <= TOLERANCE:
            return margin, True
        if best is None or rate < best[0]:
            best = (rate, margin)
    if best is None:
        # Not enough labelled items at any margin to apply the rule.
        return start, False
    return best[1], False


def short(text: str, limit: int = 100) -> str:
    flat = " ".join(text.split())
    return flat[:limit] + "..." if len(flat) > limit else flat


def print_table(scored: Scored, print_step: float, start: float, stop: float) -> None:
    counts = ", ".join(
        f"{sum(1 for item in scored.items if item.expected == name)} {name}"
        for name in scored.label_names
    )
    print(f"items: {len(scored.items)} ({counts})")
    print("margin  labelled  wrongly-sorted  sent-to-human")
    value = start
    while value <= stop + 1e-9:
        margin = round(value, 2)
        labelled, wrongly_sorted, sent_to_human = metrics(scored, margin)
        print(
            f"{margin:>5.2f}   "
            f"{labelled:>6}    "
            f"{wrongly_sorted}/{len(scored.items):<12} "
            f"{sent_to_human}/{len(scored.items)}"
        )
        value += print_step
    print()


def print_mistakes(scored: Scored, margin: float) -> None:
    """List the wrongly-sorted and sent-to-human items at one margin."""
    margins = scored.margins
    top = scored.top_names()
    wrongly = []
    human = []
    for position, item in enumerate(scored.items):
        if margins[position] < margin or top[position] in scored.never_hide:
            row = scored.scores[position]
            order = np.argsort(-row)
            second_name = scored.label_names[int(order[1])]
            human.append((item, top[position], second_name, margins[position]))
        elif top[position] != item.expected:
            wrongly.append((item, top[position], margins[position]))
    if wrongly:
        print("  wrongly-sorted (labelled, not with the expected label):")
        for item, name, item_margin in wrongly:
            print(
                f"    {short(item.text)} -> {name} "
                f"(expected {item.expected}, margin {item_margin:.3f})"
            )
    if human:
        print("  sent-to-human:")
        for item, top_name, second_name, item_margin in human:
            print(
                f"    {short(item.text)} -> {top_name} or {second_name} "
                f"(margin {item_margin:.3f})"
            )


def sample_examples(
    items: Sequence[Item], labels: Sequence[LabelDef], k: int, seed: int
) -> tuple[list[tuple[str, str]], list[Item]]:
    """Take up to k examples per label from the CSV; the rest is the test set."""
    rng = random.Random(seed)
    by_label: dict[str, list[int]] = {}
    for position, item in enumerate(items):
        by_label.setdefault(item.expected, []).append(position)
    chosen: list[tuple[str, str]] = []
    chosen_positions: set[int] = set()
    for label in labels:
        positions = by_label.get(label.name, [])
        take = min(k, len(positions))
        picked = rng.sample(positions, take) if take else []
        chosen.extend((items[position].text, label.name) for position in picked)
        chosen_positions.update(picked)
    rest = [item for position, item in enumerate(items) if position not in chosen_positions]
    return chosen, rest


def print_examples_table(
    scored: Scored,
    model,
    model_name: str,
    knn: int,
    cache_dir: Path,
    k_sizes: Sequence[int],
    seed: int,
    start: float,
    stop: float,
    resolution: float,
) -> None:
    """Sort with 5, 10 and 25 examples per label sampled from the CSV."""
    print(f"--- {', '.join(str(k) for k in k_sizes)} examples per label, sampled from the CSV (seed {seed}) ---")
    print("examples/label  test items  recommended margin  met one-in-ten  labelled  wrongly-sorted  sent-to-human")
    for k in k_sizes:
        shortage = [
            label.name for label in scored.labels
            if sum(1 for item in scored.items if item.expected == label.name) < k
        ]
        if shortage:
            print(
                f"{k:>2}             skipped: fewer than {k} labelled items for "
                f"{', '.join(shortage)}"
            )
            continue
        pool, rest_items = sample_examples(scored.items, scored.labels, k, seed)
        scores, label_names, never_hide = score_matrix(
            rest_items, pool, model, scored.labels,
            model_name=model_name, knn=knn, cache_dir=cache_dir,
        )
        probe = Scored(
            labels=scored.labels, items=rest_items, scores=scores,
            label_names=label_names, never_hide=never_hide,
        )
        margin, met = recommend_margin(probe, start, stop, resolution)
        labelled, wrongly_sorted, sent_to_human = metrics(probe, margin)
        print(
            f"{k:>2}             {len(rest_items):>10}  "
            f"{margin:>18.3f}  "
            f"{'yes' if met else 'no':>14}  "
            f"{labelled:>8}  "
            f"{wrongly_sorted}/{len(rest_items):<14} "
            f"{sent_to_human}/{len(rest_items)}"
        )
    print()


def find_folders(paths: Sequence[str]) -> list[Path]:
    folders: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_dir() and (path / "labels.yaml").exists():
            folders.append(path)
            continue
        if path.is_dir():
            folders.extend(
                sorted(
                    child for child in path.iterdir()
                    if child.is_dir() and (child / "labels.yaml").exists()
                )
            )
            continue
        raise FileNotFoundError(f"No labels.yaml found at {path}")
    return folders


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tune the margin.")
    parser.add_argument(
        "folders",
        nargs="*",
        default=["examples"],
        help="Example folders, or a parent folder (default: examples)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--print-step", type=float, default=0.02, help="Spacing of the printed table (default: 0.02)"
    )
    parser.add_argument(
        "--start", type=float, default=0.00, help="First margin tried (default: 0.00)"
    )
    parser.add_argument(
        "--stop", type=float, default=0.30, help="Last margin tried (default: 0.30)"
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=0.005,
        help="Step of the recommendation sweep (default: 0.005)",
    )
    parser.add_argument(
        "--knn", type=int, default=0,
        help="Score with k-NN of k examples per label instead of centroids",
    )
    parser.add_argument("--seed", type=int, default=7, help="Seed for the 5/10/25 example sampling (default: 7)")
    parser.add_argument(
        "--k-sizes", default="5,10,25", help="Comma-separated example counts to show (default: 5,10,25)"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Do not write margin.json"
    )
    args = parser.parse_args(argv)

    k_sizes = [int(k) for k in args.k_sizes.split(",") if k.strip()]
    if len(k_sizes) != 3:
        parser.error("--k-sizes needs three counts, for example 5,10,25")

    folders = find_folders(args.folders or ["examples"])
    model = load_model(args.model)

    for folder in folders:
        cache_dir = folder / ".hobbylm_cache"
        scored, items_file = load_scored(folder, model, args.model, args.knn, cache_dir)

        chosen, met = recommend_margin(scored, args.start, args.stop, args.resolution)
        labelled, wrongly_sorted, sent_to_human = metrics(scored, chosen)

        print(f"=== {folder.name} ===")
        print_table(scored, args.print_step, args.start, args.stop)
        if met:
            print(
                f"recommended margin: {chosen:.3f} "
                f"(labelled {labelled}/{len(scored.items)}, "
                f"wrongly-sorted {wrongly_sorted}, "
                f"sent-to-human {sent_to_human})"
            )
        else:
            print(
                f"no margin in the sweep kept wrongly-sorted items to one in ten "
                f"labelled items. The lowest rate is at margin {chosen:.3f} "
                f"(labelled {labelled}/{len(scored.items)}, "
                f"wrongly-sorted {wrongly_sorted}, "
                f"sent-to-human {sent_to_human}). A bigger handful of examples, "
                f"picked from real items, is the fix to try first."
            )
        print_mistakes(scored, chosen)
        margins = scored.margins
        print(
            "margin (top minus second): "
            f"min {margins.min():.3f}, "
            f"median {statistics.median(margins):.3f}, "
            f"max {margins.max():.3f}"
        )
        print()
        print_examples_table(
            scored, model, args.model, args.knn, cache_dir,
            k_sizes, args.seed, args.start, args.stop, args.resolution,
        )
        if args.no_save:
            print("(not saved: --no-save)")
        else:
            payload = {
                "margin": chosen,
                "met_one_in_ten": met,
                "labelled": labelled,
                "wrongly_sorted": wrongly_sorted,
                "sent_to_human": sent_to_human,
                "items": len(scored.items),
                "items_file": items_file,
                "model": args.model,
                "method": "knn" if args.knn else "centroid",
                "rule": "smallest margin with wrongly-sorted at or under one in ten "
                        "labelled items, at least ten labelled items",
            }
            out = folder / CONFIG_NAME
            out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(f"saved to {out}")
        print()

    print("This one number is a summary, not a setting to copy. A fixed margin")
    print("does not carry over between models or item sets. Set your own margin")
    print("on 30 to 50 of your own labelled items with:")
    print("    python calibrate.py path/to/your/folder")
    return 0


if __name__ == "__main__":
    sys.exit(main())
