[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/fine-tune-on-your-data/walkthrough.ipynb)

# How to fine-tune HobbyLM-Embed on your own data

This guide fine-tunes `harims95/hobbylm-embed-140m` on your own (question,
answer passage) pairs with MultipleNegativesRankingLoss, on a laptop CPU, and
saves a model folder you can load and use like the base one. Embeddings only,
no LLM.

The model is loaded through Sentence Transformers with `trust_remote_code=True`,
pinned to revision `ea708cee107818fa0c1871eebd26d82a1e3fb1aa`. Questions are
embedded with `prompt_name="query"` and passages with
`prompt_name="passage"`; the model adds its prefixes itself, so they are never
typed into your text.

Always compare the fine-tuned model against the base model on your own
held-out data before switching.

## When to fine-tune, and when not to

- Fine-tune when you have real question-passage pairs from your own domain,
  dozens to a few hundred, and you want the encoder to work on that wording.
- Do not fine-tune to compensate for missing or wrong documents. If the
  answer is not in the corpus, no embedding change fixes that.
- If the base model already does what you need, keep it. The comparison step
  below is what tells you.

## The sample data

All fictional, a made-up company's internal help wiki, in `examples/`:

- `train_pairs.csv`: 100 (query, passage) pairs to train on.
- `test_pairs.csv`: 20 held-out (query, passage_id) pairs for the comparison.
- `passages.csv`: the retrieval corpus, 170 passages: the 100 train passages,
  the 20 held-out ones, and 50 distractor pages on adjacent topics.

## Steps

### 1. Install

```bash
pip install "sentence-transformers==6.3.0" "accelerate>=1.1.0" datasets
```

### 2. Prepare your pairs

Make a CSV with the columns `query` and `passage`, one pair per row. The
column names matter: the trainer applies the model's query and passage
prompts by column name, so the prefixes stay part of the model and are never
typed into your text.

For the comparison, also keep a held-out CSV of pairs you never train on
(`test_pairs.csv` format: `query`, `passage_id` pointing into
`passages.csv`).

### 3. Train and save

```bash
python finetune.py                  # trains on examples/train_pairs.csv, saves ./my-hobbylm-embed
```

Defaults: 3 epochs, batch size 8, learning rate 2e-5, CPU. On the sample
data that is 39 steps and about a minute and a half. `--epochs 1`,
`--batch-size`, `--lr`, `--device auto` and `--train` are there if you want
them; `--hard-negatives examples/passages.csv` adds the two most confusable
corpus passages per question as extra negatives.

### 4. Compare against the base model

```bash
python evaluate.py                  # base vs fine-tuned on examples/test_pairs.csv
```

Always compare the fine-tuned model against the base model on your own
held-out data before switching. If the comparison does not go your way, keep
the base model; nothing else in this guide depends on switching.

### 5. Load and use

`my-hobbylm-embed/` is a complete Sentence Transformers model. Load it the
same way as the base one and keep the same prompt names:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("my-hobbylm-embed", trust_remote_code=True)

queries = model.encode(["office dogs, is that a thing here"], prompt_name="query")
passages = model.encode(["Dogs are welcome on the last Friday of each month."], prompt_name="passage")
```

When you load the base model itself, pin the revision:

```python
model = SentenceTransformer(
    "harims95/hobbylm-embed-140m",
    revision="ea708cee107818fa0c1871eebd26d82a1e3fb1aa",
    trust_remote_code=True,
)
```

For search, re-embed your whole corpus with the model you ship, and keep
vectors from base and fine-tuned models in separate indexes.

## Where this breaks

- **Small data fits itself.** With ~100 pairs, the model can fit the pairs
  you train on without carrying over to new questions. Keep a held-out split
  you never train on, and score both models on it.
- **Compare on your own held-out data.** Falling loss on the pairs you train
  on tells you nothing about new questions. The comparison step is the part
  of this guide that decides whether to switch.
- **Do not mix base and fine-tuned vectors in one index.** The two encoders
  are not vector-compatible. Re-embed the whole corpus with the model you
  ship, and version your index with the model that made it.
- **Keep the prompt names at serving time.** The pairs you train on carry the
  model's query and passage prefixes by column name. Encode with
  `prompt_name="query"` and `prompt_name="passage"` exactly like the base
  model, or you are serving a different task than you trained.
- **A handful of held-out questions is a small measuring tape.** Use 50 or
  more before trusting a small difference either way.

If a run misbehaves, check the pins first: sentence-transformers 6.3.0 and
model revision `ea708cee107818fa0c1871eebd26d82a1e3fb1aa`. Then check your
split: a held-out question whose twin sits in the pairs you train on makes
any comparison look better than it is.
