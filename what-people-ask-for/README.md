[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/what-people-ask-for/walkthrough.ipynb)

# What people ask for

Your feedback board has hundreds of requests and many of them are the same ask
in different words. This recipe groups an export, counts what repeats, and
writes a report you can read in one sitting. Embeddings only, no LLM. The model
is `harims95/hobbylm-embed-140m` through Sentence Transformers with
`trust_remote_code=True`; requests are embedded as plain text with no
`prompt_name`, and the unit-norm vectors make dot product cosine similarity.
Everything runs locally on CPU.

The sample data in `examples/` is fictional and clearly marked.

## Quickstart

```bash
pip install "sentence-transformers>=5" pandas scikit-learn
python piles.py examples/feature_requests/feature_requests.csv --piles examples/feature_requests/piles.yaml
python piles.py examples/support_tickets/support_tickets.csv
python calibrate.py examples
```

Each run writes `report.html` (the readable report) and `groups.csv` (one row
per request with its card and score) next to the input CSV, or pass
`--report` and `--groups-csv` to choose the paths.

## How the report is counted

Every request lands in exactly one card: a named pile, a group, or
"Doesn't fit any group". The summary line at the top of the report adds up
exactly to the rows grouped, and the code raises an error if it ever would
not. Real lines from the five examples:

```
561 requests: 144 in 3 named piles, 389 in 34 groups, 28 don't fit any group.   (feature_requests)
246 requests: 208 in 37 groups, 38 don't fit any group.                        (product_reviews)
267 requests: 225 in 36 groups, 42 don't fit any group.                        (support_tickets)
396 requests: 374 in 42 groups, 22 don't fit any group.                        (event_feedback)
299 requests: 275 in 40 groups, 24 don't fit any group.                        (talk_proposals)
```

Rows read were 585, 248, 273, 403 and 301; the difference is empty rows and
exact duplicates, which are dropped before grouping.

## Expected output

Running the quickstart's first command prints this (real run, trimmed after
the eight biggest groups):

```text
$ python piles.py examples/feature_requests/feature_requests.csv --piles examples/feature_requests/piles.yaml
585 rows read, 0 empty dropped, 24 exact duplicates dropped
561 requests: 144 in 3 named piles, 389 in 34 groups, 28 don't fit any group
  pile 'CSV export': 64 requests
  pile 'Dark mode': 70 requests
  pile 'Offline and mobile': 10 requests
  group 'tasks, pls, repeat': 53 requests
  group 'reminders, day, date': 39 requests
  group 'calendar, sync, google': 38 requests
  group 'search, save, task': 27 requests
  group 'offline, support, mode': 21 requests
  ... 29 more groups between 20 and 3 requests
  Doesn't fit any group: 28 requests
wrote examples/feature_requests/report.html
wrote examples/feature_requests/groups.csv
```

The two files land next to the input CSV. `report.html` opens with a
"Top requests" block like this (copy it straight into a planning doc):

```text
Dark mode: 70 requests (12% of 561)
CSV export: 64 requests (11% of 561)
tasks, pls, repeat (keywords): 53 requests (9% of 561)
reminders, day, date (keywords): 39 requests (7% of 561)
calendar, sync, google (keywords): 38 requests (7% of 561)
```

Every card on the page shows its count, its "How the wording repeats"
breakdown (up to 5 lines, e.g. "12 said it this way: dark mode pls"), and the
3 most different requests in the card, expandable to all of them. `groups.csv`
has one row per request: `request, group, score`, where the score is how
close the request sits to the centre of its card. Two runs on the same file
can differ by a request or two at card boundaries; the summary total and the
add-up check do not move.

Inside each card, near-duplicate wording shows up as a "how the wording
repeats" breakdown: up to 5 lines, each with a count and one wording. The 3
example quotes per card are the 3 most different requests in that card (each
one picked as the request least similar to the quotes already picked), so you
see the same ask in different words rather than three near-copies. A top-10
"Top requests" block with each card's share of the file sits at the top of the
page for copying into a planning doc. Similarity scores are in `groups.csv`,
not on the page.

## Naming piles

A pile name is just a label you choose; the example lines under it decide what
goes in. `examples/feature_requests/piles.yaml` names three piles:

```yaml
Dark mode:
  - dark mode for the app
  - a dark theme for late nights
CSV export:
  - export my tasks to a spreadsheet
  - csv export of a board
Offline and mobile:
  - a proper phone app
  - work offline on a plane
```

Requests close enough to a pile's examples (mean similarity at or above
`--pile-sim`, default 0.75) join it and keep your name. Rename the piles to
whatever you would write in a planning doc; the grouping follows the examples,
not the name.

## Checking the settings

`calibrate.py` sweeps group-size and similarity settings on the 50-row
hand-labelled sample in each example folder and prints the adjusted Rand index
against the hand labels. On the current data the peak mean ARI is 0.445 at
`cluster_sim 0.75`, the same peak the defaults in `piles.py` use
(`dedup_sim 0.92`, `cluster_sim 0.75`, `min_group 3`). Because repeated wording
is now a breakdown inside a card instead of its own card, the mean ARI table
no longer moves with `dedup_sim`: that setting only shapes the breakdown now.
Set the numbers on your own labelled sample the same way.

Per example, from the same run: `feature_requests` 0.731, `support_tickets`
0.557, `event_feedback` 0.513, `product_reviews` 0.399, and `talk_proposals`
0.200. Plain words on that last number: `talk_proposals` is the weak example.
Talk tracks barely come out of the vectors, because two proposals in the same
track can be about completely different technologies. What the recipe does
catch in a CFP pile is repeated submissions, the same talk sent twice or
reworded. Read its groups as loose technology neighbourhoods, not tracks, and
lean on the wording breakdown for the repeats.

## Limits

- Groups are based on similar wording and meaning, not on what's true or
  important. A count is how many requests repeat, not how important the ask
  is. Small groups can be noise, and a request that mixes two asks lands in
  one card, so check each card before it goes on the roadmap. Group labels are
  keywords, not summaries.
- English only.
- "Doesn't fit any group" means unlike the rest of the file, not new or
  emerging.
