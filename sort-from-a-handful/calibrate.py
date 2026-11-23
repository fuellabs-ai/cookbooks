#!/usr/bin/env python3
"""Tune the margin for sort_handful.py on your own labelled items.

Input is an example folder with a labels.yaml and a CSV of labelled items.
With a dev.csv in the folder (and --test for the held-out items), the
margin is picked on dev only and reported on test only. Without them, the
sweep and the report both run on the one CSV the folder has.

Write the items once and do not reword them after measuring. The script
scores every item, sweeps margins, prints wrongly-sorted versus
sent-to-human at each step, recommends a margin, and saves it to
margin.json next to labels.yaml.

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
the dev CSV, and reports each row on the same test items, so every
number is measured on items that were not used as examples. A count the
dev CSV cannot cover is capped with a note.

Usage:
    python calibrate.py examples
    python calibrate.py examples/github_issues --strip-templates \
        --examples-from examples/github_issues/dev.csv --per-label 10 \
        --test examples/github_issues/test.csv
    python calibrate.py examples/github_issues --strip-templates \
        --examples-from examples/github_issues/dev.csv --per-label 10 \
        --compare-methods --no-save
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
    DEFAULT_K,
    DEFAULT_METHOD,
    DEFAULT_MODEL,
    Item,
    LabelDef,
    build_example_pool,
    load_labels,
    load_items,
    load_model,
    sample_examples_from_csv,
    score_matrix,
    strip_issue_text,
)

ITEM_FILES = ["dev.csv", "items.csv", "inbox.csv", "test.csv"]
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


def check_labels(labels: Sequence[LabelDef], items: Sequence[Item], source: Path) -> None:
    known = {label.name for label in labels}
    unknown = sorted({item.expected for item in items} - known)
    if unknown:
        raise ValueError(
            f"{source}: labels {unknown} are not in labels.yaml "
            f"({sorted(known)}). The CSV and labels.yaml must use the same names."
        )


def load_labelled(
    path: Path, labels: Sequence[LabelDef], model, model_name: str,
    method: str, k: int, cache_dir: Path, strip: bool,
    example_pool: Sequence[tuple[str, str]] | None = None,
) -> Scored:
    """Score a labelled CSV, optionally against a given example pool."""
    items = load_items(path)
    unlabelled = [item for item in items if not item.expected]
    if unlabelled:
        raise ValueError(
            f"{path}: {len(unlabelled)} items have no label. Every item in a "
            "calibration CSV needs a label."
        )
    check_labels(labels, items, path)
    if strip:
        for item in items:
            item.text = strip_issue_text(item.text)
    if example_pool is None:
        example_pool = build_example_pool(labels, [])
    scores, label_names, never_hide = score_matrix(
        items, example_pool, model, labels,
        model_name=model_name, method=method, k=k, cache_dir=cache_dir,
    )
    return Scored(
        labels=list(labels), items=items, scores=scores,
        label_names=label_names, never_hide=never_hide,
    )


def cross_validated_scores(
    dev_items: Sequence[Item],
    labels: Sequence[LabelDef],
    model,
    model_name: str,
    method: str,
    k: int,
    per_label: int,
    seed: int,
    cache_dir: Path,
    strip: bool,
) -> Scored:
    """Score every dev item against a handful drawn from the other dev items.

    Leave-one-out over dev: each item is scored by examples that exclude it,
    so the margin sweep never judges an item the sorter has already seen as
    an example, and every dev item takes part.
    """
    scores = np.zeros((len(dev_items), len(labels)), dtype=np.float32)
    label_names = []
    never_hide: set[str] = set()
    for position, item in enumerate(dev_items):
        others = [x for p, x in enumerate(dev_items) if p != position]
        pool = sample_examples_from_csv(others, labels, per_label, seed)
        row_scores, names, hidden = score_matrix(
            [item], pool, model, labels,
            model_name=model_name, method=method, k=k, cache_dir=cache_dir,
        )
        scores[position] = row_scores[0]
        label_names = names
        never_hide = hidden
    return Scored(
        labels=list(labels), items=list(dev_items), scores=scores,
        label_names=label_names, never_hide=never_hide,
    )


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


def print_mistakes(scored: Scored, margin: float, limit: int = 0) -> None:
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
    if limit:
        wrongly = wrongly[:limit]
        human = human[:limit]
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
    dev_items: Sequence[Item],
    model,
    model_name: str,
    method: str,
    k: int,
    cache_dir: Path,
    test: Scored | None,
    k_sizes: Sequence[int],
    seed: int,
    margin: float,
    strip: bool,
) -> None:
    """Sort with 5, 10 and 25 examples per label from dev; report on test.

    Every row is measured on the same test items, none of which was used
    as an example. A count the dev CSV cannot cover is capped with a note.
    """
    print(f"--- {', '.join(str(k) for k in k_sizes)} examples per label, sampled from the dev CSV (seed {seed}) ---")
    if test is not None:
        print("examples/label  test items  labelled  wrongly-sorted  sent-to-human  (at the margin above)")
    else:
        print("examples/label  test items  labelled  wrongly-sorted  sent-to-human  (on the dev items not used as examples)")
    for size in k_sizes:
        shortage = [
            label.name for label in scored.labels
            if sum(1 for item in dev_items if item.expected == label.name) < size
        ]
        if shortage:
            available = sorted(
                {sum(1 for item in dev_items if item.expected == label.name)
                 for label in scored.labels}
            )
            print(
                f"{size:>2}             using every dev item: the dev CSV holds "
                f"fewer than {size} items per label ({', '.join(str(a) for a in available)})"
            )
        pool, rest_items = sample_examples(dev_items, scored.labels, size, seed)
        if strip:
            pool = [(strip_issue_text(text), name) for text, name in pool]
        target_items = test.items if test is not None else rest_items
        scores, label_names, never_hide = score_matrix(
            target_items, pool, model, scored.labels,
            model_name=model_name, method=method, k=k, cache_dir=cache_dir,
        )
        probe = Scored(
            labels=scored.labels, items=target_items, scores=scores,
            label_names=label_names, never_hide=never_hide,
        )
        labelled, wrongly_sorted, sent_to_human = metrics(probe, margin)
        print(
            f"{size:>2}             {len(target_items):>10}  "
            f"{labelled:>8}  "
            f"{wrongly_sorted}/{len(target_items):<14} "
            f"{sent_to_human}/{len(target_items)}"
        )
    print()


def print_method_comparison(
    scored: Scored,
    pool: Sequence[tuple[str, str]],
    model,
    model_name: str,
    methods: Sequence[tuple[str, int]],
    cache_dir: Path,
    start: float,
    stop: float,
    resolution: float,
) -> None:
    """Sweep two scoring methods on the same dev items and examples."""
    for method, k in methods:
        scores, label_names, never_hide = score_matrix(
            scored.items, pool, model, scored.labels,
            model_name=model_name, method=method, k=k, cache_dir=cache_dir,
        )
        probe = Scored(
            labels=scored.labels, items=scored.items, scores=scores,
            label_names=label_names, never_hide=never_hide,
        )
        margin, met = recommend_margin(probe, start, stop, resolution)
        labelled, wrongly_sorted, sent_to_human = metrics(probe, margin)
        name = f"nearest-neighbour vote k={k}" if method == "knn" else "nearest-centroid"
        print(f"--- {name} on dev ---")
        print_table(probe, 0.02, start, stop)
        print(
            f"recommended margin: {margin:.3f} "
            f"(met one-in-ten: {'yes' if met else 'no'}; "
            f"labelled {labelled}/{len(scored.items)}, "
            f"wrongly-sorted {wrongly_sorted}, "
            f"sent-to-human {sent_to_human})"
        )
        print()
    print("pick the method with the fewer wrongly-sorted and sent-to-human")
    print("items on dev, and set it as the default in sort_handful.py.")
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
        "--method", choices=["centroid", "knn"], default=None,
        help="Scoring method (default: the best of a dev comparison, or centroid)",
    )
    parser.add_argument(
        "--k", type=int, default=DEFAULT_K,
        help="Neighbours per label for --method knn (default: %(default)s)",
    )
    parser.add_argument("--compare-methods", action="store_true",
                        help="Sweep centroid and nearest-neighbour vote on the same dev items, then stop (nothing is saved)")
    parser.add_argument(
        "--test", type=Path, default=None,
        help="Held-out CSV to report on; the sweep runs on the folder's dev CSV",
    )
    parser.add_argument(
        "--examples-from", type=Path, default=None,
        help="Labelled CSV to draw the handful of examples per label from, instead of the texts in labels.yaml",
    )
    parser.add_argument(
        "--per-label", type=int, default=0,
        help="Examples per label to sample from --examples-from (0: use labels.yaml)",
    )
    parser.add_argument("--seed", type=int, default=7, help="Seed for the example sampling (default: 7)")
    parser.add_argument(
        "--k-sizes", default="5,10,25", help="Comma-separated example counts to show (default: 5,10,25)"
    )
    parser.add_argument(
        "--strip-templates", action="store_true",
        help="Strip issue-template boilerplate before embedding",
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Do not write margin.json"
    )
    args = parser.parse_args(argv)

    if args.per_label > 0 and args.examples_from is None:
        parser.error("--per-label needs --examples-from")
    k_sizes = [int(k) for k in args.k_sizes.split(",") if k.strip()]
    if len(k_sizes) != 3:
        parser.error("--k-sizes needs three counts, for example 5,10,25")

    folders = find_folders(args.folders or ["examples"])
    model = load_model(args.model)
    method = args.method
    ran_comparison = False

    for folder in folders:
        cache_dir = folder / ".hobbylm_cache"
        labels = load_labels(folder / "labels.yaml")
        dev_path = next(
            (folder / name for name in ITEM_FILES if (folder / name).exists()), None
        )
        if dev_path is None:
            raise FileNotFoundError(
                f"{folder}: needs labels.yaml and one of {', '.join(ITEM_FILES)}"
            )

        # Example source: a sampled real handful, or the texts in labels.yaml.
        if args.per_label > 0:
            source_items = load_items(args.examples_from)
            check_labels(labels, source_items, args.examples_from)
            if args.strip_templates:
                for item in source_items:
                    item.text = strip_issue_text(item.text)
            pool = build_example_pool(labels, [], examples_from=source_items, per_label=args.per_label, seed=args.seed)
            source_note = (
                f"{args.per_label} per label sampled from {args.examples_from} (seed {args.seed})"
            )
        else:
            pool = build_example_pool(labels, [])
            source_note = "the texts in labels.yaml"

        if args.per_label > 0:
            # Leave-one-out over dev: every dev item is scored against a
            # handful drawn from the other dev items, so the margin sweep
            # covers all of dev and never judges an item the sorter has
            # already seen as an example.
            dev_items = load_items(dev_path)
            if args.strip_templates:
                for item in dev_items:
                    item.text = strip_issue_text(item.text)
            sweep = cross_validated_scores(
                dev_items, labels, model, args.model,
                method or DEFAULT_METHOD, args.k, args.per_label, args.seed,
                cache_dir, args.strip_templates,
            )
        else:
            sweep = load_labelled(
                dev_path, labels, model, args.model,
                method or DEFAULT_METHOD, args.k, cache_dir, args.strip_templates,
                example_pool=pool,
            )
        if args.compare_methods:
            if ran_comparison:
                parser.error("--compare-methods takes one folder")
            print(f"=== {folder.name}: method comparison on dev, examples: {source_note} ===")
            if args.per_label > 0:
                # In the sampled-handful mode the sweep is leave-one-out over
                # dev, so each method gets its own cross-validated sweep.
                for compare_method in ("centroid", "knn"):
                    compare_items = load_items(dev_path)
                    if args.strip_templates:
                        for item in compare_items:
                            item.text = strip_issue_text(item.text)
                    compare_sweep = cross_validated_scores(
                        compare_items, labels, model, args.model,
                        compare_method, args.k, args.per_label, args.seed,
                        cache_dir, args.strip_templates,
                    )
                    name = (
                        f"nearest-neighbour vote k={args.k}"
                        if compare_method == "knn" else "nearest-centroid"
                    )
                    print(f"--- {name}, leave-one-out over dev ---")
                    print_table(compare_sweep, args.print_step, args.start, args.stop)
                    m, met = recommend_margin(compare_sweep, args.start, args.stop, args.resolution)
                    lab, wrong, human = metrics(compare_sweep, m)
                    print(
                        f"recommended margin: {m:.3f} "
                        f"(met one-in-ten: {'yes' if met else 'no'}; "
                        f"labelled {lab}/{len(compare_sweep.items)}, "
                        f"wrongly-sorted {wrong}, "
                        f"sent-to-human {human})"
                    )
                    print()
            else:
                print_method_comparison(
                    sweep, pool, model, args.model,
                    [("centroid", args.k), ("knn", args.k)],
                    cache_dir, args.start, args.stop, args.resolution,
                )
            print("pick the method with the fewer wrongly-sorted and sent-to-human")
            print("items on dev, and set it as the default in sort_handful.py.")
            print()
            ran_comparison = True
            continue

        if method is None:
            method = DEFAULT_METHOD

        chosen, met = recommend_margin(sweep, args.start, args.stop, args.resolution)
        labelled, wrongly_sorted, sent_to_human = metrics(sweep, chosen)

        print(f"=== {folder.name} ===")
        print(f"examples: {source_note}")
        print_table(sweep, args.print_step, args.start, args.stop)
        if met:
            print(
                f"recommended margin on dev: {chosen:.3f} "
                f"(labelled {labelled}/{len(sweep.items)}, "
                f"wrongly-sorted {wrongly_sorted}, "
                f"sent-to-human {sent_to_human})"
            )
        else:
            print(
                f"no margin in the sweep kept wrongly-sorted items to one in ten "
                f"labelled items on dev. The lowest rate is at margin {chosen:.3f} "
                f"(labelled {labelled}/{len(sweep.items)}, "
                f"wrongly-sorted {wrongly_sorted}, "
                f"sent-to-human {sent_to_human}). A bigger handful of examples, "
                f"picked from real items, is the fix to try before anything else."
            )
        print_mistakes(sweep, chosen)
        margins = sweep.margins
        print(
            "margin (top minus second): "
            f"min {margins.min():.3f}, "
            f"median {statistics.median(margins):.3f}, "
            f"max {margins.max():.3f}"
        )
        print()

        test = None
        if args.test is not None:
            test = load_labelled(
                args.test, labels, model, args.model,
                method, args.k, cache_dir, args.strip_templates,
                example_pool=pool,
            )
            t_labelled, t_wrong, t_human = metrics(test, chosen)
            print(
                f"--- report on {args.test} at the margin above: "
                f"labelled {t_labelled}/{len(test.items)}, "
                f"wrongly-sorted {t_wrong}, "
                f"sent-to-human {t_human} ---"
            )
            print_mistakes(test, chosen)
            print()

        print_examples_table(
            sweep, sweep.items, model, args.model, method, args.k,
            cache_dir, test, k_sizes, args.seed, chosen, args.strip_templates,
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
                "items": len(sweep.items),
                "dev_file": dev_path.name,
                "test_file": args.test.name if args.test else "",
                "model": args.model,
                "method": method,
                "k": args.k,
                "examples": source_note,
                "picked_on": (
                    "dev, leave-one-out: each dev item scored against a handful "
                    "drawn from the other dev items"
                    if args.per_label > 0 else
                    "dev, all items scored against the labels.yaml examples"
                ),
                "strip_templates": args.strip_templates,
                "rule": "smallest margin with wrongly-sorted at or under one in ten "
                        "labelled items, at least ten labelled items; picked on dev only",
            }
            out = folder / CONFIG_NAME
            out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(f"saved to {out}")
        print()

    print("This one number is a summary, not a setting to copy. A fixed margin")
    print("does not carry over between models or item sets. Set your own margin")
    print("on your own dev items, and report on held-out items only, with:")
    print("    python calibrate.py path/to/your/folder --test path/to/test.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
