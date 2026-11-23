#!/usr/bin/env python3
"""Pick the fill, check and margin thresholds on the dev split only.

The queries of each example were split into dev and test once, with seed 7,
before any tuning. This script sweeps the settings on the dev split, keeps
the best pair, writes examples/<name>/thresholds.json, and can then score
the untouched test split and the hard cases with the chosen settings.

Usage:
    python calibrate.py examples/shoe_store                # sweep on dev
    python calibrate.py examples/shoe_store --test         # score the test split
    python calibrate.py examples/shoe_store --hard-cases   # score the hard cases
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Sequence

from fill_filters import (
    Matcher,
    assign,
    evaluate_batch,
    load_catalog,
    load_model,
    print_report,
)

HI_GRID = [round(0.25 + 0.025 * i, 3) for i in range(13)]   # 0.25 .. 0.55
LO_GRID = [round(0.15 + 0.025 * i, 3) for i in range(15)]   # 0.15 .. 0.50
MARGIN_GRID = [0.02, 0.05, 0.10]
MODES = ["prompt", "plain"]
DEFAULT_TODAY = date(2026, 12, 1)


def load_queries(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sweep(catalog: dict, matcher_cache: dict[str, list[dict]], dev: list[dict]):
    """Sweep mode, hi, lo and margin on cached dev analyses."""
    results = []
    for mode in MODES:
        analyses = matcher_cache[mode]
        for hi in HI_GRID:
            for lo in LO_GRID:
                if lo >= hi:
                    continue
                for margin in MARGIN_GRID:
                    filled_queries = []
                    for analysis in analyses:
                        filters, check, _text = assign(
                            analysis, catalog, hi, lo, margin
                        )
                        filled_queries.append(
                            {k: v for k, v in filters.items() if v}
                        )
                    report = evaluate_batch(
                        dev, [_fake_result(q, f, c) for q, f, c in
                              zip(dev, filled_queries,
                                  [_chips(a, catalog, hi, lo, margin)
                                   for a in analyses])]
                    )
                    results.append({
                        "mode": mode, "hi": hi, "lo": lo, "margin": margin,
                        "correct": report["correct"], "wrong": report["wrong"],
                        "false_fills": report["false_fills"],
                        "chip_hits": report["chip_hits"],
                    })
    results.sort(
        key=lambda r: (-r["correct"], r["false_fills"], -r["chip_hits"],
                       r["hi"], r["lo"])
    )
    return results


def _fake_result(row: dict, filters: dict, check: list[dict]) -> dict:
    return {"query": row["text"], "filters": filters, "check": check,
            "search_text": "", "negated": [], "rule_fills": []}


def _chips(analysis, catalog, hi, lo, margin):
    _f, check, _t = assign(analysis, catalog, hi, lo, margin)
    return check


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sweep thresholds on dev, score test and hard cases."
    )
    parser.add_argument("folder", help="Example folder with catalog.yaml")
    parser.add_argument("--test", action="store_true", help="Score queries_test.csv")
    parser.add_argument("--hard-cases", action="store_true", help="Score hard_cases.csv")
    parser.add_argument("--today", default=None, help="Base date YYYY-MM-DD")
    args = parser.parse_args(argv)

    folder = Path(args.folder)
    catalog = load_catalog(folder / "catalog.yaml")
    today = date.fromisoformat(args.today) if args.today else DEFAULT_TODAY

    if args.test or args.hard_cases:
        name = "queries_test.csv" if args.test else "hard_cases.csv"
        rows = load_queries(folder / name)
        thresholds = json.loads((folder / "thresholds.json").read_text(encoding="utf-8"))
        start = time.perf_counter()
        model = load_model()
        matcher = Matcher(catalog, model, thresholds["mode"])
        results = [
            matcher.match(r["text"], today, thresholds["hi"], thresholds["lo"],
                          thresholds["margin"])
            for r in rows
        ]
        elapsed = time.perf_counter() - start - 0  # model load included
        report = evaluate_batch(rows, results)
        print(f"{folder.name}/{name}: mode {thresholds['mode']}, "
              f"hi {thresholds['hi']}, lo {thresholds['lo']}, "
              f"margin {thresholds['margin']}")
        print(f"run time: {elapsed:.1f} s on cpu including model load")
        print_report(report)
        return 0

    dev = load_queries(folder / "queries_dev.csv")
    n_values = sum(len(s["values"]) for s in catalog["filters"].values()
                   if s["type"] == "enum")
    print(f"{folder.name}: {len(dev)} dev queries, {n_values} catalog values")
    matcher_cache: dict[str, list[dict]] = {}
    for mode in MODES:
        start = time.perf_counter()
        model = load_model()
        load_time = time.perf_counter() - start
        start = time.perf_counter()
        matcher = Matcher(catalog, model, mode)
        matcher_cache[mode] = [matcher.analyse(r["text"], today) for r in dev]
        print(f"embedded dev phrases in {mode} mode: "
              f"{time.perf_counter() - start:.1f} s "
              f"(model load {load_time:.1f} s)")
    start = time.perf_counter()
    results = sweep(catalog, matcher_cache, dev)
    sweep_time = time.perf_counter() - start
    best = results[0]
    print(f"sweep of {len(results)} settings took {sweep_time:.1f} s")
    print("top 5 on dev:")
    for r in results[:5]:
        print(f"  mode {r['mode']:5s} hi {r['hi']:.3f} lo {r['lo']:.3f} "
              f"margin {r['margin']:.2f} -> correct {r['correct']}/20, "
              f"false fills {r['false_fills']}, chips right {r['chip_hits']}")
    prompt_best = next(r for r in results if r["mode"] == "prompt")
    plain_best = next(r for r in results if r["mode"] == "plain")
    print(f"best prompted:  correct {prompt_best['correct']}/20, "
          f"false fills {prompt_best['false_fills']}")
    print(f"best plain:     correct {plain_best['correct']}/20, "
          f"false fills {plain_best['false_fills']}")
    print(f"chosen: mode {best['mode']}, hi {best['hi']}, lo {best['lo']}, "
          f"margin {best['margin']}")
    (folder / "thresholds.json").write_text(
        json.dumps({k: best[k] for k in ("mode", "hi", "lo", "margin")},
                   indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {folder / 'thresholds.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
