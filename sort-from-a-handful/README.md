# Sort from a handful

Show it a few examples per label and it sorts the rest. When it is not sure, it
puts the item in "needs a human" instead of guessing. No training run, no API
key, runs on CPU. Embeddings only: `harims95/hobbylm-embed-140m` through
Sentence Transformers with `trust_remote_code=True`, plain text with no
`prompt_name`, unit-norm vectors.

## Quickstart

```bash
pip install "sentence-transformers>=5"
python sort_handful.py examples/github_issues/items.csv --labels examples/github_issues/labels.yaml
python sort_handful.py examples/github_issues/items.csv --labels examples/github_issues/labels.yaml --corrections examples/github_issues/corrections.csv
python calibrate.py examples/github_issues
python sort_handful.py examples/careers_inbox/inbox.csv --labels examples/careers_inbox/labels.yaml
python sort_handful.py examples/school_admissions/inbox.csv --labels examples/school_admissions/labels.yaml
```

Each run writes `sorted.csv` (text, label, score, margin, needs_human, plus the
expected label when the input has one) and `report.html` next to the input CSV.

`--corrections` takes a CSV with `text` and `label` columns, appends those rows
as new examples, rebuilds the centroids and sorts again. `calibrate.py` sweeps
the margin, recommends the smallest margin that keeps wrongly-sorted items at or
under one in ten labelled items, and writes it to `margin.json`.

`.github/workflows/label-issues.example.yml` is a GitHub Action that labels new
issues on CPU with no secrets beyond the default `GITHUB_TOKEN`. It only labels.
It never closes an issue, never comments, never assigns.

## Where the github_issues data came from

`examples/github_issues/items.csv` holds 200 closed issues from
[scikit-learn/scikit-learn](https://github.com/scikit-learn/scikit-learn)
(BSD-3 licence), 50 per label. The labels are the maintainers' own: `bug`,
`documentation`, `question`, `new feature`. They were sampled from the public
GitHub API on 21 November 2026: closed issues with the label, no pull requests,
a body of at least 80 characters, 50 picked per label with seed 7. Each row
keeps the URL of its issue. The issue texts remain under the scikit-learn
project's BSD-3 licence.

`examples/github_issues/labels.yaml` is a fictional starting point: 5 example
texts per label, written by hand. The `careers_inbox` and `school_admissions`
inboxes are fictional sample data written for this recipe.

## Limits

It sorts by topic and wording, not intent. Labels that differ mostly in intent
or tone (a new lead vs a vendor pitch, an agency CV vs spam) will blur, and the
margin can be wrong both ways, so set it on your own items and keep a person on
anything urgent or sensitive. English only. It labels; it never acts.
