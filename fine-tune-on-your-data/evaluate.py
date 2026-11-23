#!/usr/bin/env python3
"""Compare the base model and the fine-tuned model on the held-out questions.

Embeddings only, no LLM. Both models run through the exact same setup: the
same 20 held-out (query, passage) pairs, the same 170-passage corpus, query
side embedded with prompt_name="query", passage side with prompt_name="passage",
ranked by dot product (vectors are unit-norm, so that is cosine similarity).
Reported metrics are recall@1, recall@5 and MRR.

Run after finetune.py has produced ./my-hobbylm-embed:

    python evaluate.py                 # base vs fine-tuned
    python evaluate.py --base-only     # just the base model
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import transformers

transformers.logging.set_verbosity_error()
transformers.utils.logging.disable_progress_bar()

from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "harims95/hobbylm-embed-140m"
MODEL_REVISION = "ea708cee107818fa0c1871eebd26d82a1e3fb1aa"
DEFAULT_FT = "my-hobbylm-embed"
DEFAULT_TEST = "examples/test_pairs.csv"
DEFAULT_PASSAGES = "examples/passages.csv"


def read_test(csv_path: Path) -> list[tuple[str, str]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [(r["query"].strip(), r["passage_id"].strip()) for r in csv.DictReader(f)]


def read_passages(csv_path: Path) -> list[tuple[str, str]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [(r["passage_id"].strip(), r["passage"].strip()) for r in csv.DictReader(f)]


def evaluate(model: SentenceTransformer, test: list[tuple[str, str]], passages: list[tuple[str, str]]) -> dict:
    queries = [q for q, _ in test]
    gold = [pid for _, pid in test]
    passage_ids = [pid for pid, _ in passages]
    texts = [p for _, p in passages]

    q_emb = model.encode(queries, prompt_name="query", batch_size=32, convert_to_numpy=True)
    p_emb = model.encode(texts, prompt_name="passage", batch_size=32, convert_to_numpy=True)

    sims = q_emb @ p_emb.T  # unit-norm vectors: dot product is cosine similarity
    hits_at_1 = hits_at_5 = 0
    reciprocal_ranks: list[float] = []
    for row, pid in zip(sims, gold):
        order = sorted(range(len(passage_ids)), key=lambda j: -row[j])
        rank = order.index(passage_ids.index(pid)) + 1
        hits_at_1 += rank == 1
        hits_at_5 += rank <= 5
        reciprocal_ranks.append(1.0 / rank)
    n = len(test)
    return {
        "n": n,
        "corpus": len(passages),
        "recall@1": hits_at_1 / n,
        "recall@5": hits_at_5 / n,
        "mrr": sum(reciprocal_ranks) / n,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--test", type=Path, default=Path(DEFAULT_TEST))
    ap.add_argument("--passages", type=Path, default=Path(DEFAULT_PASSAGES))
    ap.add_argument("--base", default=DEFAULT_MODEL, help="base model name or path")
    ap.add_argument("--ft", type=Path, default=Path(DEFAULT_FT), help="fine-tuned model folder")
    ap.add_argument("--base-only", action="store_true", help="evaluate only the base model")
    ap.add_argument("--device", default="cpu", help='"cpu" (default) or "auto"')
    args = ap.parse_args()

    test = read_test(args.test)
    passages = read_passages(args.passages)
    print(f"{len(test)} held-out questions, {len(passages)} passages in the corpus\n")

    rows: list[tuple[str, dict]] = []

    base = SentenceTransformer(args.base, revision=MODEL_REVISION, trust_remote_code=True, device=args.device)
    t0 = time.perf_counter()
    base_metrics = evaluate(base, test, passages)
    base_metrics["seconds"] = time.perf_counter() - t0
    rows.append((f"base ({DEFAULT_MODEL.rsplit('/', 1)[-1]} @{MODEL_REVISION[:8]})", base_metrics))
    del base

    if not args.base_only:
        ft = SentenceTransformer(str(args.ft), trust_remote_code=True, device=args.device)
        t0 = time.perf_counter()
        ft_metrics = evaluate(ft, test, passages)
        ft_metrics["seconds"] = time.perf_counter() - t0
        rows.append((f"fine-tuned ({args.ft})", ft_metrics))

    header = f"{'model':44} {'recall@1':>9} {'recall@5':>9} {'MRR':>7} {'embed s':>8}"
    print(header)
    for name, m in rows:
        print(
            f"{name:44} {m['recall@1']:>9.2f} {m['recall@5']:>9.2f} "
            f"{m['mrr']:>7.3f} {m['seconds']:>8.1f}"
        )
    print("\nrecall@k: share of held-out questions whose gold passage is in the top k. "
          "MRR: mean of 1/rank of the gold passage.")


if __name__ == "__main__":
    main()
