#!/usr/bin/env python3
"""Tune the two score cut-offs for show_me.py on your own labelled questions.

Input is a CSV with a question column and a label column, where the label is
"answerable" or "unanswerable". Write the questions once and do not reword
them after measuring. The script scores every question, sweeps cut-offs,
prints wrong answers versus wrong refusals at each step, recommends an upper
and a lower cut-off, reports how many questions land in "Check this", and
saves both cut-offs to cutoff.json in the docs folder.

Usage:
    python calibrate.py examples/support_refund_policy
    python calibrate.py examples
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from show_me import (
    CONFIG_NAME,
    DEFAULT_MODEL,
    DocumentIndex,
    load_model,
    read_questions_csv,
)


@dataclass
class ScoredQuestion:
    question: str
    answerable: bool
    top1: float
    top_section: str


def load_questions(folder: Path) -> list[dict]:
    path = folder / "questions.csv"
    if not path.exists():
        raise FileNotFoundError(f"No questions.csv in {folder}")
    rows = read_questions_csv(path)
    if not all(row["label"] for row in rows):
        raise ValueError(
            f"{path}: every question needs a label of answerable or unanswerable"
        )
    return rows


def score_folder(folder: Path, model, model_name: str) -> tuple[DocumentIndex, list[ScoredQuestion]]:
    rows = load_questions(folder)
    index = DocumentIndex.build(folder, model=model, model_name=model_name)
    scores = index.score_all([row["question"] for row in rows])

    scored: list[ScoredQuestion] = []
    for position, row in enumerate(rows):
        row_scores = scores[position]
        top_index = int(np.argmax(row_scores))
        chunk = index.chunks[top_index]
        scored.append(
            ScoredQuestion(
                question=row["question"],
                answerable=row["label"] == "answerable",
                top1=float(row_scores[top_index]),
                top_section=chunk.label,
            )
        )
    return index, scored


def metrics(rows: Sequence[ScoredQuestion], cutoff: float) -> tuple[int, int]:
    wrong_answers = sum(1 for row in rows if not row.answerable and row.top1 >= cutoff)
    wrong_refusals = sum(1 for row in rows if row.answerable and row.top1 < cutoff)
    return wrong_answers, wrong_refusals


def recommend_cutoffs(
    rows: Sequence[ScoredQuestion], start: float, stop: float, resolution: float
) -> tuple[float, float, int, int, int]:
    """Pick the two cut-offs from the labelled questions.

    The upper cut-off is the smallest one where wrong answers reach their
    floor, so unanswerable questions stop being answered as early as
    possible. The lower cut-off is the largest one where wrong refusals
    reach their floor, so answerable questions stop being refused as late
    as possible. Everything between the two lands in "Check this".

    Returns upper, lower, wrong answers, wrong refusals and the number of
    questions in the Check this band.
    """
    steps = round((stop - start) / resolution)
    grid = [round(start + step * resolution, 3) for step in range(steps + 1)]

    wrong_answers_at = {cutoff: metrics(rows, cutoff)[0] for cutoff in grid}
    wrong_refusals_at = {cutoff: metrics(rows, cutoff)[1] for cutoff in grid}

    floor_wrong_answers = wrong_answers_at[grid[-1]]
    upper = next(cutoff for cutoff in grid if wrong_answers_at[cutoff] == floor_wrong_answers)

    floor_wrong_refusals = wrong_refusals_at[grid[0]]
    lower = max(
        cutoff for cutoff in grid if cutoff <= upper
        and wrong_refusals_at[cutoff] == floor_wrong_refusals
    )

    in_band = sum(1 for row in rows if lower <= row.top1 < upper)
    return upper, lower, wrong_answers_at[upper], wrong_refusals_at[lower], in_band


def save_cutoff(
    folder: Path, upper: float, lower: float, wrong_answers: int,
    wrong_refusals: int, check_count: int, model_name: str,
    rows: Sequence[ScoredQuestion]
) -> Path | None:
    answerable_count = sum(1 for row in rows if row.answerable)
    path = folder / CONFIG_NAME
    payload = {
        "upper": upper,
        "lower": lower,
        "wrong_answers": wrong_answers,
        "wrong_refusals": wrong_refusals,
        "check_this": check_count,
        "answerable": answerable_count,
        "unanswerable": len(rows) - answerable_count,
        "model": model_name,
        "questions_file": "questions.csv",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def print_mistakes(rows: Sequence[ScoredQuestion], upper: float, lower: float) -> None:
    wrong_answers = [row for row in rows if not row.answerable and row.top1 >= upper]
    wrong_refusals = [row for row in rows if row.answerable and row.top1 < lower]
    in_band = [row for row in rows if lower <= row.top1 < upper]
    if wrong_answers:
        print("  wrong answers (unanswerable, scored at or above the upper cut-off):")
        for row in wrong_answers:
            print(f"    {row.question} (top1 {row.top1:.3f}, {row.top_section})")
    if wrong_refusals:
        print("  wrong refusals (answerable, scored below the lower cut-off):")
        for row in wrong_refusals:
            print(f"    {row.question} (top1 {row.top1:.3f}, {row.top_section})")
    if in_band:
        print("  check this (between the cut-offs):")
        for row in in_band:
            print(f"    {row.question} (top1 {row.top1:.3f}, {row.top_section})")
    if not wrong_answers and not wrong_refusals and not in_band:
        print("  no questions land between the cut-offs and no mistakes at these cut-offs")


def score_summary(rows: Sequence[ScoredQuestion]) -> str:
    answerable = [row.top1 for row in rows if row.answerable]
    unanswerable = [row.top1 for row in rows if not row.answerable]
    parts = []
    if answerable:
        parts.append(
            "answerable top1: "
            f"min {min(answerable):.3f}, "
            f"median {statistics.median(answerable):.3f}, "
            f"max {max(answerable):.3f}"
        )
    if unanswerable:
        parts.append(
            "unanswerable top1: "
            f"min {min(unanswerable):.3f}, "
            f"median {statistics.median(unanswerable):.3f}, "
            f"max {max(unanswerable):.3f}"
        )
    return "\n".join(parts)


def print_table(
    folder_name: str,
    rows: Sequence[ScoredQuestion],
    print_step: float = 0.05,
    start: float = 0.30,
    stop: float = 0.95,
) -> None:
    answerable_count = sum(1 for row in rows if row.answerable)
    unanswerable_count = len(rows) - answerable_count
    print(f"=== {folder_name} ===")
    print(
        f"questions: {len(rows)} "
        f"({answerable_count} answerable, {unanswerable_count} unanswerable)"
    )
    print("cut-off  wrong answers  wrong refusals  total")
    value = start
    while value <= stop + 1e-9:
        cutoff = round(value, 2)
        wrong_answers, wrong_refusals = metrics(rows, cutoff)
        print(
            f"{cutoff:>5.2f}    "
            f"{wrong_answers}/{unanswerable_count:<14} "
            f"{wrong_refusals}/{answerable_count:<15} "
            f"{wrong_answers + wrong_refusals}"
        )
        value += print_step
    print()


def print_aggregate_table(
    rows: Sequence[ScoredQuestion],
    print_step: float = 0.05,
    start: float = 0.30,
    stop: float = 0.95,
) -> None:
    answerable_count = sum(1 for row in rows if row.answerable)
    unanswerable_count = len(rows) - answerable_count
    print("=== all examples ===")
    print(
        f"questions: {len(rows)} "
        f"({answerable_count} answerable, {unanswerable_count} unanswerable)"
    )
    print("cut-off  wrong answers  wrong refusals  total")
    value = start
    while value <= stop + 1e-9:
        cutoff = round(value, 2)
        wrong_answers, wrong_refusals = metrics(rows, cutoff)
        print(
            f"{cutoff:>5.2f}    "
            f"{wrong_answers}/{unanswerable_count:<14} "
            f"{wrong_refusals}/{answerable_count:<15} "
            f"{wrong_answers + wrong_refusals}"
        )
        value += print_step
    print()


def find_example_folders(paths: Sequence[str]) -> list[Path]:
    folders: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_dir() and (path / "questions.csv").exists():
            folders.append(path)
            continue
        if path.is_dir():
            folders.extend(
                sorted(
                    child for child in path.iterdir()
                    if child.is_dir() and (child / "questions.csv").exists()
                )
            )
            continue
        raise FileNotFoundError(f"No questions.csv found at {path}")
    return folders


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tune the score cut-off.")
    parser.add_argument(
        "folders",
        nargs="*",
        default=["examples"],
        help="Example folders, or a parent folder (default: examples)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--print-step", type=float, default=0.05, help="Spacing of the printed table"
    )
    parser.add_argument(
        "--start", type=float, default=0.30, help="First cut-off tried (default: 0.30)"
    )
    parser.add_argument(
        "--stop", type=float, default=0.95, help="Last cut-off tried (default: 0.95)"
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=0.005,
        help="Step of the recommendation sweep (default: 0.005)",
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Do not write cutoff.json"
    )
    args = parser.parse_args(argv)

    folders = find_example_folders(args.folders or ["examples"])
    model = load_model(args.model)
    all_rows: list[ScoredQuestion] = []
    summaries = []

    for folder in folders:
        index, rows = score_folder(folder, model, args.model)
        all_rows.extend(rows)
        upper, lower, wrong_answers, wrong_refusals, in_band = recommend_cutoffs(
            rows, args.start, args.stop, args.resolution
        )
        answerable_count = sum(1 for row in rows if row.answerable)
        summaries.append(
            {
                "folder": folder.name,
                "chunks": len(index.chunks),
                "answerable": answerable_count,
                "unanswerable": len(rows) - answerable_count,
                "recommended_upper": upper,
                "recommended_lower": lower,
                "wrong_answers": wrong_answers,
                "wrong_refusals": wrong_refusals,
                "check_this": in_band,
                "answerable_top1": sorted(row.top1 for row in rows if row.answerable),
                "unanswerable_top1": sorted(
                    row.top1 for row in rows if not row.answerable
                ),
            }
        )

        print_table(folder.name, rows, print_step=args.print_step, start=args.start, stop=args.stop)
        print(
            f"recommended cut-offs: upper {upper:.3f}, lower {lower:.3f} "
            f"(wrong answers {wrong_answers}/{len(rows) - answerable_count}, "
            f"wrong refusals {wrong_refusals}/{answerable_count}, "
            f"check this {in_band}/{len(rows)})"
        )
        print_mistakes(rows, upper, lower)
        print(score_summary(rows))
        if args.no_save:
            print("(not saved: --no-save)")
        else:
            saved = save_cutoff(
                folder, upper, lower, wrong_answers, wrong_refusals, in_band,
                args.model, rows,
            )
            print(f"saved to {saved}")
        print()

    global_upper, global_lower, global_wrong_answers, global_wrong_refusals, global_in_band = recommend_cutoffs(
        all_rows, args.start, args.stop, args.resolution
    )
    print_aggregate_table(all_rows, print_step=args.print_step, start=args.start, stop=args.stop)
    print(f"chunks across examples: {sum(item['chunks'] for item in summaries)}")
    print(f"cut-offs across all examples: upper {global_upper:.3f}, lower {global_lower:.3f}")
    print(
        f"wrong answers: {global_wrong_answers}, "
        f"wrong refusals: {global_wrong_refusals}, "
        f"check this: {global_in_band}, "
        f"total: {global_wrong_answers + global_wrong_refusals + global_in_band}"
    )
    print(score_summary(all_rows))
    print()
    print("This one pair is a summary, not a setting to copy. A fixed cut-off")
    print("does not carry over between models or document sets. Set your own")
    print("cut-offs from 30 to 50 of your own labelled questions with:")
    print("    python calibrate.py path/to/your/docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
