# Show me where it says that

A HobbyLM-Embed cookbook for checking answers against your own documents.

Your help bot just promised a refund your policy doesn't offer. This checks
every answer against your own documents first, and tells you when the answer
isn't there.

Before a support bot or RAG app sends an answer, this recipe looks for the
section in your own documents that backs it up. Two cut-offs give three
verdicts:

- **Found**: the top section scores at or above the upper cut-off. The
  recipe returns that section with its file and heading, so a human can read
  it in one click.
- **Check this**: the score lands between the two cut-offs. The recipe shows
  the top section and says a person should confirm it. Nothing gets answered
  automatically on a borderline score.
- **Not in these documents**: the top section scores below the lower
  cut-off. The recipe shows the 3 nearest sections labelled "closest, but
  not an answer" and adds the question to a gaps list.

In 2024, a Canadian tribunal ordered Air Canada to pay CA$812 after its
chatbot gave a customer incorrect information about bereavement fares
([Moffatt v. Air Canada, 2024 BCCRT 149](https://decisions.civilresolutionbc.ca/crt/crtd/en/item/525448/index.do)).

## Who this is for

- **The support lead switching on a help bot.** Person: whoever owns the
  bot. Document: your refund, returns and shipping pages. Moment: before the
  bot sends an answer to a customer. Worry: the bot promises something the
  policy does not offer, and the promise becomes a claim against you.
- **The engineer wiring retrieval into a RAG app.** Person: the developer of
  the app. Document: the folder the app retrieves from. Moment: between
  retrieval and the answer step. Worry: the retriever returns a plausible
  section that does not actually answer the question.
- **The support agent answering tickets by hand.** Person: the agent.
  Document: the internal knowledge base. Moment: when a customer asks
  something the knowledge base never covered. Worry: answering from memory
  and getting the number wrong.
- **The documentation manager.** Person: whoever owns the doc set.
  Document: the doc set itself. Moment: the weekly review of what users
  asked. Worry: questions that keep landing in the gaps list with no article
  written for them.
- **The security reviewer.** Person: the person filling in customer security
  questionnaires. Document: past answered questionnaires. Moment: when a new
  form arrives with a control you have never answered. Worry: promising a
  certification the company does not hold.

Also useful for checking a batch of user-submitted questions before they
reach an answering step. Also useful for screening a document set for topics
with no coverage. Also useful for giving a reviewer the exact file and
heading behind any claim.

## What is in this folder

- `show_me.py`: the CLI. One question, or a batch from a CSV.
- `calibrate.py`: tunes the two cut-offs on your own labelled questions and
  saves them to a config file.
- `walkthrough.ipynb`: the same recipe in a notebook with an Open in Colab
  badge.
- `examples/`: five fictional document sets. Each has 4 to 8 short documents
  and a `questions.csv` with 10 answerable and 10 unanswerable questions.
  The unanswerable questions sound close to real content on purpose.
- `show_me_output/`: real batch outputs from the runs in this README.

The sample companies and policies in `examples/` are fictional. They exist
to test the recipe, not to describe a real product.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install "sentence-transformers>=5" pypdf python-docx
```

The CLI example from this cookbook's title:

```bash
python show_me.py examples/support_refund_policy "can I get a refund after 30 days?"
```

Real output, cut-offs calibrated on the labelled questions (upper 0.775,
lower 0.680):

```
Check this
  sympathy-and-bereavement-orders.md > Sympathy and bereavement orders > Documentation for refunds (0.735)
  For a refund on a sympathy order that could not be delivered on time, we ask for the funeral home name and the service time. A photo of the arrangement is not needed when the delivery was refused or the venue closed. Refunds follow the same 3 to 5 working d...
  A person should confirm this section answers the question.

Added to check_this.md: examples/support_refund_policy/check_this.md
```

Plainly: with the single cut-off this question used to come back Found, at
0.735 against a 0.730 cut-off, which was a wrong answer because no section
describes a 30 day refund window. With two cut-offs it lands in Check this,
which matches the documents: refund sections score close, none of them
answers it, and a person should confirm before anyone repeats a number.

A question the documents do answer:

```bash
python show_me.py examples/support_refund_policy "How long does a refund take to reach my card?"
```

```
Found
  refunds-and-freshness.md > Refunds and freshness > How long a refund takes (0.817)
  Card refunds are requested the same working day we approve them. Your bank usually posts the money in 3 to 5 working days, and some banks take up to 10. Refunds to a PayPal balance can take up to 30 days to show.
  also near:
  refunds-and-freshness.md > Refunds and freshness > Late deliveries (0.724)
    If a guaranteed next-day delivery arrives later than the paid-for window, we refund the delivery fee on request. The standard delivery fee is not refundable when the parcel arrives within the estimated window shown at checkout.
  sympathy-and-bereavement-orders.md > Sympathy and bereavement orders > Documentation for refunds (0.723)
    For a refund on a sympathy order that could not be delivered on time, we ask for the funeral home name and the service time. A photo of the arrangement is not needed when the delivery was refused or the venue closed. Refunds follow the same 3 to 5 working d...
```

And one that is genuinely absent:

```bash
python show_me.py examples/support_refund_policy "Do you offer gift cards that never expire?"
```

```
Not in these documents
  closest, but not an answer:
  returns-and-substitutions.md > Returns and substitutions > Made to order (0.653)
    Every bouquet is cut and arranged after you order, so we do not accept returns. If something is wrong with the arrangement, the freshness guarantee in Refunds and freshness applies instead.
  returns-and-substitutions.md > Returns and substitutions > Vases and packaging (0.639)
    Vases and gift packaging can be swapped before the arrangement is made if you contact us before 6 pm the day before delivery. Vases that arrive broken are replaced free of charge; send a photo within 48 hours.
  returns-and-substitutions.md > Returns and substitutions > Substitutions (0.633)
    When a stem is out of season, our florists substitute a flower of equal or greater value in a similar colour. Substitutions are listed on the delivery note. If you do not accept substitutions, tick "no substitutions" at checkout and we will contact you befo...

Added to gaps.md: examples/support_refund_policy/gaps.md
```

## Try it in Colab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/hobbylm-embed-cookbook/blob/main/show-me-where/walkthrough.ipynb)

The notebook clones `fuellabs-ai/hobbylm-embed-cookbook`, folder
`show-me-where`, at branch `main`. The clone constants sit in one setup cell
(`REPO`, `BRANCH`, `FOLDER`), and a local copy of `show_me.py` short-circuits
the clone so the notebook also runs from a checkout.

## Batch mode: results.csv, gaps.md and check_this.md

```bash
python show_me.py examples/support_refund_policy \
    --questions examples/support_refund_policy/questions.csv --out-dir output
```

Real summary from that run:

```
questions: 20
found: 6
check this: 10
not in these documents: 4
```

`results.csv` has one row per question:

```
question,label,verdict,top_section,score
Can I get a refund if my flowers arrive wilted?,answerable,Check this,refunds-and-freshness.md > Refunds and freshness > What we cannot refund,0.741
How long does a refund take to reach my card?,answerable,Found,refunds-and-freshness.md > Refunds and freshness > How long a refund takes,0.817
What happens if nobody is home when the bouquet is delivered?,answerable,Check this,delivery-and-shipping.md > Delivery and shipping > When nobody answers,0.680
Do you sell preserved roses that last a year?,unanswerable,Not in these documents,returns-and-substitutions.md > Returns and substitutions > Substitutions,0.664
```

## How it works

1. Parse each file to text. Markdown and text use heading lines. HTML uses
   the Python standard library. PDF uses `pypdf`. DOCX uses `python-docx`.
2. Split by heading, then into chunks under 220 words. A word is about 1.3
   tokens in English, so a chunk is around 290 tokens, well under the
   model's 1,024 token limit. Each chunk keeps its file name and heading.
3. Embed every chunk with `prompt_name="passage"` and cache the vectors by
   model name and chunk text. An edited file gets a new cache key.
4. Embed the question with `prompt_name="query"` and score every chunk by
   dot product. Vectors are unit-norm, so this is cosine similarity.
5. Compare the top score with two cut-offs. At or above the upper cut-off
   the verdict is `Found` and the recipe returns that section with file and
   heading. Below the lower cut-off the verdict is `Not in these documents`,
   the three nearest sections are shown labelled `closest, but not an
   answer`, and the question goes to the gaps list. Between the two, the
   verdict is `Check this`: the top section is shown and a person should
   confirm it.

The model is `harims95/hobbylm-embed-140m` through Sentence Transformers
with `trust_remote_code=True`. Embeddings only: no LLM writes an answer. The
model adds the `passage: ` and `query: ` prefixes itself, so never type
those prefixes into the text you pass in.

## The gaps list and the Check this list

Only questions answered "Not in these documents" go to `gaps.md`. Those are
questions the documents do not answer anywhere near well enough, and they
read as missing articles: `gaps.md` groups them by the section they scored
highest against, and a group with several questions under one section is a
hint for an article that does not exist yet.

Real `gaps.md` from the batch run above:

```markdown
# Gaps in examples/support_refund_policy

4 of 20 questions are not answered by these documents (lower cut-off 0.680,
upper cut-off 0.775).

Each group below starts with the section that scored highest against
those questions. A group with several questions under one section is
a hint for an article that does not exist yet.

## returns-and-substitutions.md > Returns and substitutions > Substitutions

- Do you sell preserved roses that last a year? (score 0.664)
- Do you have a price match against other florists? (score 0.596)

## payment-and-invoicing.md > Payment and invoicing > One discount per order

- Do you offer a first-order discount for new accounts? (score 0.660)

## returns-and-substitutions.md > Returns and substitutions > Made to order

- Do you offer gift cards that never expire? (score 0.653)
```

Questions in the Check this band get their own list, `check_this.md`, in the
same grouped shape, with a reminder that a person should confirm each one.
The first three groups of the real `check_this.md` from the same batch run
(the file continues with six more groups):

```markdown
# Check this list for examples/support_refund_policy

10 of 20 questions landed between the two cut-offs (lower 0.680, upper 0.775).

A person should confirm each of these. The section listed under a
question is the one that scored highest; it sounds close, but it may
not answer the question.

## returns-and-substitutions.md > Returns and substitutions > Made to order

- Can I get a refund on a bouquet I picked up myself and did not like the colour of? (score 0.774)
- Can I return a vase I bought in your shop? (score 0.708)

## refunds-and-freshness.md > Refunds and freshness > Late deliveries

- Can I get a refund if I miss the delivery window myself? (score 0.771)

## returns-and-substitutions.md > Returns and substitutions > Substitutions

- Do you deliver flowers in August? (score 0.680)
```

Single-question runs append one line at a time to the matching list in the
docs folder: refusals to `gaps.md`, borderline scores to `check_this.md`.
Paths inside the quoted files above are shortened for readability; the
written files carry the full docs folder path in their title line.

## Calibrate the cut-offs on your own questions

`calibrate.py` reads a CSV of your own questions labelled `answerable` or
`unanswerable`, scores them, sweeps cut-offs, prints wrong answers versus
wrong refusals at each step, recommends a pair of cut-offs, reports how many
questions land in Check this, and saves both to `cutoff.json` in the docs
folder. `show_me.py` picks that file up automatically; `--upper` and
`--lower` override it.

The two cut-offs are picked from opposite ends of the mistake trade-off:

- the **upper** cut-off is the smallest one where wrong answers reach their
  floor, so unanswerable questions stop being answered as early as possible;
- the **lower** cut-off is the largest one where wrong refusals reach their
  floor, so answerable questions stop being refused as late as possible;
- everything between the two is Check this.

A fixed cut-off does not carry over between models or document sets. Set the
pair from 30 to 50 of your own questions, written once and not reworded
after measuring.

```bash
python calibrate.py examples/support_refund_policy
```

Real recommendation lines from all five example folders:

```
council_services:              upper 0.745, lower 0.645  (wrong answers 0/10, wrong refusals 0/10, check this 12/20)
developer_docs:                upper 0.740, lower 0.670  (wrong answers 0/10, wrong refusals 0/10, check this 10/20)
employee_handbook:             upper 0.705, lower 0.625  (wrong answers 0/10, wrong refusals 0/10, check this 6/20)
security_questionnaire_library: upper 0.780, lower 0.720 (wrong answers 0/10, wrong refusals 0/10, check this 6/20)
support_refund_policy:         upper 0.775, lower 0.680  (wrong answers 0/10, wrong refusals 0/10, check this 10/20)
```

At these pairs the sample data has no wrong answers and no wrong refusals.
The cost is the Check this band: 44 of the 100 sample questions land there
instead of getting an automatic answer or refusal.

### The sweep tables behind the recommendations

Each table is from 20 questions per folder: 10 answerable, 10 unanswerable.
"Wrong answers" counts unanswerable questions that scored at or above a
single cut-off. "Wrong refusals" counts answerable questions that scored
below it. These single-cutoff numbers are what the two recommendations are
read from.

`support_refund_policy`:

| Cut-off | Wrong answers | Wrong refusals | Total |
| ---: | ---: | ---: | ---: |
| 0.60 | 9/10 | 0/10 | 9 |
| 0.65 | 9/10 | 0/10 | 9 |
| 0.70 | 4/10 | 1/10 | 5 |
| 0.75 | 2/10 | 2/10 | 4 |
| 0.80 | 0/10 | 5/10 | 5 |
| 0.85 | 0/10 | 9/10 | 9 |

`council_services`:

| Cut-off | Wrong answers | Wrong refusals | Total |
| ---: | ---: | ---: | ---: |
| 0.60 | 9/10 | 0/10 | 9 |
| 0.65 | 6/10 | 1/10 | 7 |
| 0.70 | 5/10 | 3/10 | 8 |
| 0.75 | 0/10 | 5/10 | 5 |
| 0.80 | 0/10 | 9/10 | 9 |

`security_questionnaire_library`:

| Cut-off | Wrong answers | Wrong refusals | Total |
| ---: | ---: | ---: | ---: |
| 0.60 | 7/10 | 0/10 | 7 |
| 0.65 | 4/10 | 0/10 | 4 |
| 0.70 | 1/10 | 0/10 | 1 |
| 0.75 | 1/10 | 4/10 | 5 |
| 0.80 | 0/10 | 10/10 | 10 |

`employee_handbook`:

| Cut-off | Wrong answers | Wrong refusals | Total |
| ---: | ---: | ---: | ---: |
| 0.55 | 9/10 | 0/10 | 9 |
| 0.60 | 5/10 | 0/10 | 5 |
| 0.65 | 2/10 | 1/10 | 3 |
| 0.70 | 1/10 | 1/10 | 2 |
| 0.75 | 0/10 | 4/10 | 4 |
| 0.80 | 0/10 | 7/10 | 7 |

`developer_docs`:

| Cut-off | Wrong answers | Wrong refusals | Total |
| ---: | ---: | ---: | ---: |
| 0.60 | 7/10 | 0/10 | 7 |
| 0.65 | 5/10 | 0/10 | 5 |
| 0.70 | 1/10 | 5/10 | 6 |
| 0.75 | 0/10 | 6/10 | 6 |
| 0.80 | 0/10 | 7/10 | 7 |

### What moved where, compared with the single cut-off

With the single cut-off (0.730 on the lead example, 0.675 to 0.755 across
examples) the sample data had 6 wrong answers and 11 wrong refusals. All 6
wrong answers and all 11 wrong refusals now land in Check this:

- "can I get a refund after 30 days?" (0.735), the CLI example, previously
  Found at the single cut-off and not in any question set;
- "Can I get a refund on a bouquet I picked up myself and did not like the
  colour of?" (0.774) and "Can I get a refund if I miss the delivery window
  myself?" (0.771), previously wrong answers in support_refund_policy;
- "Do you have a Go SDK?" (0.689) and "Do webhooks work with self-signed
  certificates?" (0.736), previously wrong answers in developer_docs;
- "Can we connect our VPN to your admin console?" (0.777), previously a
  wrong answer in security_questionnaire_library;
- the 5 previously-wrong refusals in council_services ("Can I pay council
  tax over 12 months?" 0.646, "How do visitor parking permits work?" 0.743,
  "What help is there if I cannot pay my council tax?" 0.655, "Who do I
  contact if I might be homeless in two months?" 0.704, "Can I take a
  trailer to the recycling centre at the weekend?" 0.657), the 1 in
  employee_handbook ("What equipment do I get for working from home?"
  0.626) and the 1 in developer_docs ("What does error 429 mean?" 0.674).

The band also moves some answerable questions out of Found. In
support_refund_policy, "Can I get a refund if my flowers arrive wilted?"
(0.741) was Found at the single cut-off and is now Check this. A person
confirming it costs a click; a bot promising a refund the policy does not
offer costs more. That is the trade the Check this band makes on purpose.

The example cut-off pairs range from 0.625/0.705 to 0.720/0.780 on the same
model. That spread is the reason a cut-off from one document set does not
transfer to another.

## Limits

The "not in these documents" decision is a score cut-off, not understanding. It will sometimes say no when the answer is there, and sometimes show a close-sounding section that does not answer the question, so set the cut-off on your own questions and keep a person in the loop for anything involving money, law or health.

Product catalogs are hard: a question about a size or spec the page does not list, such as "Summit Boots in wide widths", can still score close to that product's page at 0.729.

The Check this band narrows where that limit bites: borderline scores go to
a person instead of becoming a yes or a no. It does not remove the limit,
because the two cut-offs are still score cut-offs.

Two more limits: the recipe is English only, and it finds sections rather
than writing answers. The section it returns is for a person to read, not a
sentence to paste.

## Reproducing the numbers

Everything in this README comes from runs on the machine that built the
cookbook: `calibrate.py examples` produced the tables and the recommendation
lines, and the batch runs in `show_me_output/` produced the results files.
The Colab notebook runs the same commands from a fresh clone.
