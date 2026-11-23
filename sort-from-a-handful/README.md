# Sort from a handful

Show it a few examples per label and it sorts the rest. When it isn't sure, it puts the item in "needs a human" instead of guessing. No training run, no API key, runs on CPU.

Pairs with the [What people keep asking for](../what-people-ask-for/) cookbook: first see what people say, name the groups, then sort everything that comes next into them.

The sample companies, schools and messages in `examples/` are fictional, except `examples/github_issues`, which holds real issues with real maintainer labels (source below).

## Who this is for

- Open source maintainers who want new issues labelled `bug`, `question` and friends before they read them.
- Recruiters and HR teams watching a shared careers@ address, where a referral from your own engineer should not get lost under agency CVs.
- School admissions offices sharing an admissions@ address, where a complaint must reach a person no matter what.

Also useful for, with no worked files here: CRM inbound triage, travel guest messages, and public grievance desks working in English.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install sentence-transformers pyyaml

python sort_handful.py examples/careers_inbox/inbox.csv --labels examples/careers_inbox/labels.yaml
python calibrate.py examples
```

[Open the walkthrough in Colab](https://colab.research.google.com/github/fuellabs-ai/hobbylm-embed-cookbook/blob/main/sort-from-a-handful/walkthrough.ipynb) (notebook: [walkthrough.ipynb](walkthrough.ipynb)).

The model is HobbyLM-Embed 140M through Sentence Transformers with `trust_remote_code=True`. Classification passes plain text with no `prompt_name`. Vectors are unit-norm, so dot products are cosine similarities. Embeddings only: no LLM, no fine-tuning.

## How it works

1. `labels.yaml` gives each label a handful of example texts, about 5 to start. A label can carry `never_hide: true`: items whose top label has it are still labelled, but they are always flagged `needs_human`, because that label must reach a person. `careers_inbox` does this for `referral`, `school_admissions` for `complaint`.
2. Each new item is scored against every label. By default each label is the unit-norm mean of its examples (nearest-centroid); `--method knn --k 5` switches to a nearest-neighbour vote (the mean similarity to the k nearest examples of each label). The margin is the top score minus the second score. If the margin clears the threshold, the item gets the top label. If not, it goes to "needs a human" with the top 2 labels shown.
3. Corrections loop: move an item to the right label, put it in a CSV with `text` and `label` columns, and pass it with `--corrections`. It is appended as a new example, the centroids are rebuilt, and the run repeats. Copy the correction into `labels.yaml` to keep it.
4. Batch mode on a CSV only. There is no watch mode. Each run writes `sorted.csv` (text, label, score, margin, needs_human, plus the expected label when the input has one) and `report.html` with the per-label table, the deferred items with their top 2 labels, and every wrong sort.
5. The margin is a setting. `calibrate.py` recommends one from dev items only and saves it to `margin.json` next to `labels.yaml`. A fixed margin does not carry over between models or item sets.
6. `--strip-templates` removes issue-template boilerplate before embedding. It is off by default because most inboxes are not issue trackers.

## The real dataset in examples/github_issues

- Source: closed issues from [scikit-learn/scikit-learn](https://github.com/scikit-learn/scikit-learn), pulled through the public GitHub API on 21 November 2026.
- Licence: the repository is BSD-3-Clause; the issue text was written and published by its authors on GitHub under GitHub's terms of service.
- Labels: the maintainers' own labels, kept verbatim (lowercased): `bug`, `documentation`, `question`, `new feature`. The recipe's story says "feature request"; scikit-learn's maintainers call that label `new feature`, and the data keeps their name.
- Sampling: closed issues with the label, no pull requests, a body of at least 80 characters, 50 picked per label with `random.Random(7)`, text = title plus body, capped at 1,500 characters. 200 items in `items.csv` with `number`, `label`, `text`, `url`.
- Split, made once with seed 7 and stratified: 50 dev issues in `dev.csv` (13 bug, 13 documentation, 12 question, 12 new feature), 150 test issues in `test.csv` (37, 37, 38, 38). The margin is picked on dev only. Every reported number below is measured on the same 150 test issues. No test issue is ever used as an example.
- `labels.yaml` next to them is fictional: 5 example texts per label written by hand, kept as a clearly named second run ("fictional handful" in the table below). No example text was taken from the dataset.

## Stripping the issue-template boilerplate

`--strip-templates` removes markdown headings, template prompts like "Describe the workflow you want to enable" and "Steps/Code to Reproduce", HTML comments, placeholder `_No response_` answers, the maintainer-workflow warning that templates paste in, and empty checklist lines. The title and the person's own words stay. Across the 200 issues the stripped text keeps a median of 93 percent of the characters.

Three issues, before and after:

1. Expected label `documentation`:

   > Before: `DOC: n_jobs parameter in LogisticRegression missing inline deprecation notice > [!WARNING] > This issue is not yet ready for a PR. If you are interested in contributing to scikit-learn, please have a look at our [contributing guidelines](https://scikit-learn.org/dev/developers/contributing.html), and in particular the sections for [new contributors]...`
   >
   > After: `DOC: n_jobs parameter in LogisticRegression missing inline deprecation notice > Add the deprecation notice inline in the n_jobs parameter description block in sklearn/linear_model/_logistic.py. Change from: ...`

2. Expected label `new feature`:

   > Before: `Optional return of reduced distances in neighbors.Tree.query > [!WARNING] > This issue is not yet ready for a PR. ... ### Describe the workflow you want to enable ...`
   >
   > After: `Optional return of reduced distances in neighbors.Tree.query > I like them squared. For tree.query(return_distances=True) ... add an option to get reduced distances. ...`

3. Expected label `question`:

   > Before: `how class_weight or sample_weight passed and used for imbalanced classification? <!-- **If your issue is a usage question, please submit it in one of these other channels instead:** - **StackOverflow with the scikit-learn tag: ...** ...`
   >
   > After: `how class_weight or sample_weight passed and used for imbalanced classification? I was trying to track down how the parameter class_weight and sample_weight passed and used in classification. ...`

One honest finding from the runs below: stripping removes the template headings, and those headings partly leaked the label (a "Describe the workflow you want to enable" heading travels with feature requests, a "Describe the bug" heading with bugs). Removing them is the right thing for a general recipe, and it exposes how much these four labels blur in the person's own words: stripping does not reduce the number of wrong sorts on this dataset.

## Picking the margin on dev only

The margin must come from dev, but the 10-examples-per-label handful is itself sampled from dev, so scoring dev items against their own examples would flatter the sorter. `calibrate.py` therefore scores dev leave-one-out: every dev item is scored against a handful drawn from the other dev items, and the sweep runs on those 50 scores.

Method comparison on dev, same items, same 10-examples-per-label handful, leave-one-out, stripping on:

| margin | centroid: labelled / wrong / sent | nearest-neighbour vote k=5: labelled / wrong / sent |
| ---: | :---: | :---: |
| 0.00 | 50, 23 wrong, 0 sent | 50, 27 wrong, 0 sent |
| 0.02 | 18, 7, 32 | 18, 7, 32 |
| 0.04 | 2, 0, 48 | 3, 1, 47 |

Nearest-centroid wins and stays the default: at margin 0 it mislabels 23 of 50 dev items against 27 for the vote, and at its recommended margin it labels more items (26 against 13) with fewer items a person must handle (32 against 42). With a centroid, ten real examples average into one steadier point per label; the vote follows individual nearest examples, and on long technical texts the nearest example is a less stable judge.

No margin in either sweep kept wrongly-sorted items to one in ten labelled items, so the rule says so and takes the margin with the lowest wrongly-sorted rate among margins with at least ten labelled items: **0.010** for the centroid (26 labelled, 8 wrong, 24 sent on dev). `margin.json` records that the rule was not met. One margin is used for every row below, on dev's authority alone.

## The table: both handfuls, with and without stripping

All rows on the same 150 test issues, at margin 0.010, nearest-centroid. The real handfuls are sampled from dev with seed 7; the "25" row caps at what dev has (every dev item, 13/13/12/12 per label). The fictional handful is `labels.yaml`, 5 hand-written texts per label.

| handful | examples per label | stripping | labelled | wrongly sorted | sent to a person |
| :--- | ---: | :---: | ---: | ---: | ---: |
| fictional | 5 | off | 95 | 27/150 | 55/150 |
| fictional | 5 | on | 102 | 36/150 | 48/150 |
| real | 5 | off | 97 | 34/150 | 53/150 |
| real | 5 | on | 91 | 37/150 | 59/150 |
| real | 10 | off | 88 | 31/150 | 62/150 |
| real | 10 | on | 73 | 30/150 | 77/150 |
| real | every dev item | off | 80 | 21/150 | 70/150 |
| real | every dev item | on | 75 | 25/150 | 75/150 |

Read on this table:

- The operating point (real handful of 10, stripping on) labels 73 of 150 and sends 77, so 51 percent of the test set still goes to a person. Among the 73 labelled items, 30 carry the wrong label (41 percent). Do not read the "labelled" column as quality.
- Stripping did not reduce wrong sorts on this dataset, and it moved items into the queue: the template headings it removes carried real label signal, and their removal is paid for in caution. It is still the right default for a general recipe, because a new issue's own words are what a maintainer reads and a template that leaks labels will not exist in every tracker.
- More examples per label lower the wrong count somewhat (21 wrong with every dev item, stripping off, against 31 with 10 per label) while sending more to a person. Going from 5 to 10 to every dev item changes the shape of the trade, not its difficulty: these four labels differ mostly by intent, and the wording alone does not separate them.

## What the operating point did on test

`python sort_handful.py examples/github_issues/test.csv --labels examples/github_issues/labels.yaml --strip-templates --examples-from examples/github_issues/dev.csv --per-label 10`, margin 0.010 from `margin.json`, nearest-centroid:

- 150 test issues: 73 labelled, 77 sent to a person, 30 wrongly sorted.
- Worst confusions among the 30: `documentation` read as `question` (5), `bug` as `question` (4), `documentation` as `new feature` (4), `new feature` as `question` (4), `question` as `bug` (4).

Five of the wrong sorts, with text (all 30 are in `report.html`):

| got | expected | text |
| --- | --- | --- |
| question | bug | radius_neighbors with array radius works with n_jobs=1 but raises ValueError for n_jobs>1 When `radius` is passed as a per-sample array, `NearestNeighbors.radius_neighbors` returns a correct result with `n_jobs=1` but raises a `ValueError` with `n_jobs>1` on identical input. |
| documentation | bug | Automatic main lock-file update fails for debian-32 build I can reproduce locally, no clue where this is coming from: python build_tools/update_environments_and_lock_files.py --select-build debian_32 -vvv. |
| documentation | bug | HTML repr: keyboard focus is invisible on the expand/collapse toggles (WCAG 2.4.7) Hi! I'm Eya, a full-stack developer with a Research Master's in ICT. I use scikit-learn in my machine learning work and I'm interested in the accessibility of the HTML repr. |
| question | bug | `UnionFind.fast_find`'s path compression never touches the queried node, so path compression is effectively a no-op there. |
| question | bug | FeatureAgglomeration.inverse_transform fails on list/DataFrame input, including its own set_output result. I work in AI, ML, DS and use scikit-learn for preprocessing and modeling pipelines, usually with set_output(transform="pandas"). |

Corrections loop on the same test set, with the same margin: 3 dev items the sorter mislabelled during the dev sweep are moved to their right label and appended as examples. The queue shrinks (77 to 70) but wrong sorts rise (30 to 35): at this margin the three corrections did not pay for themselves yet. The loop is how the example set grows over time, not a one-shot fix, and nothing was tuned further to make the demo look better.

## Calibrate on your own items

```bash
python calibrate.py path/to/your/folder --test path/to/test.csv
```

It prints, per margin: labelled, wrongly-sorted, sent-to-human. Then the recommendation (with the leave-one-out note when the examples are sampled from dev), the wrongly-sorted items, the deferred items, and the 5/10/25 table on the same test items. It saves the margin to `margin.json`:

```json
{
  "margin": 0.01,
  "met_one_in_ten": false,
  "labelled": 26,
  "wrongly_sorted": 8,
  "sent_to_human": 24,
  "items": 50,
  "dev_file": "dev.csv",
  "test_file": "test.csv",
  "model": "harims95/hobbylm-embed-140m",
  "method": "centroid",
  "k": 5,
  "examples": "10 per label sampled from examples/github_issues/dev.csv (seed 7)",
  "picked_on": "dev, leave-one-out: each dev item scored against a handful drawn from the other dev items",
  "strip_templates": true,
  "rule": "smallest margin with wrongly-sorted at or under one in ten labelled items, at least ten labelled items; picked on dev only"
}
```

The recommendation rule: the smallest margin at which wrongly-sorted items are at most one in ten of the labelled items, counting only margins with at least ten labelled items. If no margin manages that, the script says so and takes the margin with the lowest wrongly-sorted rate instead. Wrong labels are the failure mode; a human check is a cost, not a mistake. Write your items once and do not reword them after measuring.

## The fictional inboxes

### careers_inbox: fictional careers@ inbox, 30 messages

Margin 0.020 (from its own `margin.json`, picked on the same 30 messages): 20 labelled, 10 sent to a person, 2 wrongly sorted. `referral` has `never_hide: true`, so 3 referrals went to a person even when the sorter was sure. The moment of the example holds: every agency CV pitch was either labelled `agency cv` or sent to a person, and no referral was buried under one.

Every wrong sort, shown openly:

| got | expected | text |
| --- | --- | --- |
| direct application | referral | My old flatmate Tomasz built the flight controller at AeroWorks and I think he would be great for your firmware opening. |
| direct application | interview scheduling | I applied for the firmware role two weeks ago and have not heard back. Could you confirm my application arrived and tell me the timeline for next steps? |

Both are the blur the Limits section predicts: a person applying on a tip reads like a direct application, and a status chase reads like an application. The margin put six of the blurriest messages in the queue with their top 2 labels (mostly `direct application` or `referral`), which is where a person wanted them.

### school_admissions: fictional admissions@ inbox, 30 messages

Margin 0.000 (the sweep found nothing wrong to guard against): 24 labelled, 6 sent to a person, 0 wrongly sorted. The 6 in the queue are the complaints, there because of `never_hide: true`, not because the sorter was unsure.

## The GitHub Action

`.github/workflows/label-issues.example.yml` runs on new issues, on CPU, with no secrets beyond the default `GITHUB_TOKEN`. It sorts the issue text against `labels.yaml`, adds the winning label, and adds `needs-triage` as well when the sorter is unsure or the top label has `never_hide: true`. It only labels. It never closes an issue, never comments, never assigns.

To use it in your own repository: copy `sort_handful.py` to the root, put `labels.yaml` (and `margin.json`, optional) at the root, set `SORTER_DIR` to `.` and `LABELS_FILE` to `labels.yaml` in the workflow. The model is cached between runs with `actions/cache` into a local `hobbylm-model-cache` folder, so the second run skips the download.

Run time, measured on this development machine's CPU (Apple M4, no GPU, warm model cache in the Hugging Face cache): model load 4.6 s, scoring one issue against the handful 0.9 s, so the sort step is about 5.5 s. With a cold cache the model download plus load took 75.2 s (538 MB), which the cache step pays once instead of per issue. The workflow prints its own elapsed seconds in the log, and GitHub runner times will differ from a laptop.

## Limits

It sorts by topic and wording, not intent. Labels that differ mostly in intent or tone (a new lead vs a vendor pitch, an agency CV vs spam) will blur, and the margin can be wrong both ways, so set it on your own items and keep a person on anything urgent or sensitive. English only. It labels; it never acts.

## A note on the fictional numbers

The careers and admissions messages are fictional, written once and not adjusted after measuring. Accuracy on fictional data mostly measures how clearly we wrote it: the admissions set was written with sharply separated wording, so it sorts cleanly; the careers set was written with deliberate blur between referral and direct application and between agency CV and spam, so it shows those blurs. Neither number predicts your inbox.

## Files

- `sort_handful.py`: the CLI. `python sort_handful.py items.csv --labels labels.yaml`, with `--margin`, `--method`, `--k`, `--corrections`, `--strip-templates`, `--examples-from`, `--per-label`.
- `calibrate.py`: the margin sweep on dev and the 5/10/25 table on test. `python calibrate.py examples`.
- `labels.yaml`: the fictional handful, with optional `never_hide: true`.
- `examples/github_issues/dev.csv`, `test.csv`: the fixed 50/150 split (seed 7), plus `corrections.csv` for the loop demo.
- `walkthrough.ipynb`: the executed walkthrough, with an Open in Colab badge.
- `.github/workflows/label-issues.example.yml`: the labelling Action described above.
- `examples/careers_inbox`, `examples/school_admissions`: the fictional inboxes, each with `sorted.csv`, `report.html` and `margin.json` from the runs in this README.
