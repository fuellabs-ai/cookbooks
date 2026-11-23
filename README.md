# HobbyLM-Embed cookbooks

Six small cookbooks for the [HobbyLM-Embed](https://huggingface.co/harims95/hobbylm-embed-140m) embedding model. Each folder holds a script, sample data and a walkthrough notebook. Everything runs locally on CPU. Embeddings only, no LLM.

## The cookbooks

| Cookbook | What it does | Who it's for | Embedding task | Try it |
|---|---|---|---|---|
| [What really changed in v2?](what-changed/) | Compares two versions of a document clause by clause and reports only the changes that altered meaning. | Marketers, store owners, account managers | Semantic similarity | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/what-changed/walkthrough.ipynb) |
| [No more "trust me bro"](show-me-where/) | Checks an answer against your own documents and points to the section that backs it up, or says the answer is not there. | Support leads, RAG developers, security reviewers | Retrieval, with a "not found" answer | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/show-me-where/walkthrough.ipynb) |
| [Show a few, it sorts the rest](sort-from-a-handful/) | Sorts new items into labels from about five examples per label and sends the ones it is unsure about to a person. | Recruiters, admissions offices, open source maintainers | Few-shot classification | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/sort-from-a-handful/walkthrough.ipynb) |
| [What are users really asking for?](what-people-ask-for/) | Groups a feedback export into named piles and similar groups, and counts how often each ask repeats. | Product managers, product owners, support leads | Clustering and near-duplicate grouping | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/what-people-ask-for/walkthrough.ipynb) |
| [Fine-tune on your own data](fine-tune-on-your-data/) | How to fine-tune the model on your own question and passage pairs on CPU, save it, and compare it against the base model on your own held-out data before switching. | Search engineers, support teams, ML engineers | Fine-tuning for retrieval | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/fine-tune-on-your-data/walkthrough.ipynb) |
| [Type it once, the filters fill in](type-it-once/) | Fills a site's search filters from one typed sentence: rules handle numbers, prices, sizes, guest counts and dates, negation is checked before matching, and the model matches the remaining phrases to the catalog's own values. | Online stores, hotel booking, travel search | Matching phrases to a fixed list of values | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/type-it-once/walkthrough.ipynb) |

## The model

`harims95/hobbylm-embed-140m`: 140M total parameters, 36M active (excluding embeddings), 512-dimensional vectors, English. See [AGENTS.md](AGENTS.md) for load settings and tested thresholds, and each folder's README for its quickstart.

## License

[Apache-2.0](LICENSE)
