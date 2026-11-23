#!/usr/bin/env python3
"""Fine-tune HobbyLM-Embed on your own (query, passage) pairs.

Embeddings only, no LLM. The model is HobbyLM-Embed 140M loaded through
Sentence Transformers with trust_remote_code=True, pinned to revision
ea708cee107818fa0c1871eebd26d82a1e3fb1aa, and trained with
MultipleNegativesRankingLoss: every batch contributes the other rows as
negatives, so plain question-passage pairs are enough to start.

The CSV must have the columns `query` and `passage`. Those names match the
model's prompt names, so the model's query and passage prefixes are applied
to the right column automatically during training. The prefixes are part of
the model and are never written into your text by hand. Training runs on CPU
by default; on the sample data it takes a couple of minutes.

With --hard-negatives PATH (a passages.csv with passage_id,passage columns),
the two corpus passages that the base model confuses most with each gold
passage are added to every row as extra negatives.

Usage:
    python finetune.py [--train examples/train_pairs.csv] [--out my-hobbylm-embed]
    python finetune.py --hard-negatives examples/passages.csv

Afterwards, compare the fine-tuned model against the base model on your own
held-out data (see evaluate.py) before switching.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import transformers

transformers.logging.set_verbosity_error()
transformers.utils.logging.disable_progress_bar()

from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
)
from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss

DEFAULT_MODEL = "harims95/hobbylm-embed-140m"
MODEL_REVISION = "ea708cee107818fa0c1871eebd26d82a1e3fb1aa"
DEFAULT_TRAIN = "examples/train_pairs.csv"
DEFAULT_OUT = "my-hobbylm-embed"


def read_pairs(csv_path: Path) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = [
            {"query": (r["query"] or "").strip(), "passage": (r["passage"] or "").strip()}
            for r in csv.DictReader(f)
        ]
    rows = [r for r in rows if r["query"] and r["passage"]]
    if not rows:
        raise SystemExit(f"no (query, passage) rows found in {csv_path}")
    return rows


def read_corpus(csv_path: Path) -> list[tuple[str, str]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [(r["passage_id"].strip(), r["passage"].strip()) for r in csv.DictReader(f)]


def mine_hard_negatives(
    model: SentenceTransformer, pairs: list[dict], corpus: list[tuple[str, str]], per_question: int = 2
) -> list[dict]:
    """For each pair, add the corpus passages the base model confuses most with the gold."""
    texts = [p for _, p in corpus]
    q_emb = model.encode([r["query"] for r in pairs], prompt_name="query", convert_to_numpy=True)
    p_emb = model.encode(texts, prompt_name="passage", convert_to_numpy=True)
    sims = q_emb @ p_emb.T

    rows = []
    for i, pair in enumerate(pairs):
        order = sorted(range(len(texts)), key=lambda j: -sims[i][j])
        negatives, seen = [], {pair["passage"]}
        for j in order:
            if texts[j] in seen:
                continue
            seen.add(texts[j])
            negatives.append(texts[j])
            if len(negatives) == per_question:
                break
        row = dict(pair)
        for n, neg in enumerate(negatives, 2):
            row[f"passage_{n}"] = neg
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--train", type=Path, default=Path(DEFAULT_TRAIN), help="CSV with query,passage columns")
    ap.add_argument("--out", type=Path, default=Path(DEFAULT_OUT), help="output folder for the fine-tuned model")
    ap.add_argument("--hard-negatives", type=Path, default=None,
                    help="optional passages CSV (passage_id,passage); mines 2 hard negatives per question from it")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="base model to start from")
    ap.add_argument("--epochs", type=float, default=3.0, help="passes over the training pairs (1 to 3 is right for ~100 pairs)")
    ap.add_argument("--batch-size", type=int, default=8, help="rows per step; also the number of in-batch negatives per row minus one")
    ap.add_argument("--lr", type=float, default=2e-5, help="learning rate")
    ap.add_argument("--device", default="cpu", help='"cpu" (default) or "auto" to let torch pick cuda/mps')
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    pairs = read_pairs(args.train)

    model = SentenceTransformer(
        args.model, revision=MODEL_REVISION, trust_remote_code=True, device=args.device
    )
    model.max_seq_length = 512

    if args.hard_negatives:
        corpus = read_corpus(args.hard_negatives)
        pairs = mine_hard_negatives(model, pairs, corpus)
        print(f"{len(pairs)} training rows, 2 hard negatives each mined from {args.hard_negatives}")
        # extra columns must carry the model's passage prefix; reuse it instead of typing it
        extra = ("passage_2", "passage_3")
        model.prompts.update({name: model.prompts["passage"] for name in extra})
    else:
        print(f"{len(pairs)} training pairs from {args.train}")
    print(f"prompts applied during training: {model.prompts}")

    dataset = Dataset.from_list(pairs)  # column names query/passage* match the prompt names
    loss = MultipleNegativesRankingLoss(model)
    targs = SentenceTransformerTrainingArguments(
        output_dir=args.out.parent / ".finetune_trainer_tmp",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.lr,
        warmup_steps=0.1,  # transformers v5: a float here means the warmup ratio
        seed=args.seed,
        use_cpu=args.device == "cpu",
        logging_steps=5,
        save_strategy="no",
        report_to=[],
        disable_tqdm=True,
    )
    trainer = SentenceTransformerTrainer(model, args=targs, train_dataset=dataset, loss=loss)

    t0 = time.perf_counter()
    trainer.train()
    minutes = time.perf_counter() - t0
    print(f"training took {minutes / 60:.1f} min on {args.device}")

    model.save(str(args.out))
    print(f"saved to {args.out}/")
    print(f"reload it with: SentenceTransformer(\"{args.out}\", trust_remote_code=True)")


if __name__ == "__main__":
    main()
