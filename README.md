# HobbyLM-Embed cookbooks

Four small cookbooks for the [HobbyLM-Embed](https://huggingface.co/harims95/hobbylm-embed-140m) embedding model. Each folder holds a script, sample data and a walkthrough notebook. Everything runs locally on CPU. Embeddings only, no LLM.

## The cookbooks

| Cookbook | What it does | Who it's for | Embedding task | Try it |
|---|---|---|---|---|
| [What really changed in v2?](what-changed/) | Compares two versions of a document clause by clause and reports only the changes that altered meaning. | Marketers, store owners, account managers | Semantic similarity | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/what-changed/walkthrough.ipynb) |
| [No more "trust me bro"](show-me-where/) | Checks an answer against your own documents and points to the section that backs it up, or says the answer is not there. | Support leads, RAG developers, security reviewers | Retrieval, with a "not found" answer | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/show-me-where/walkthrough.ipynb) |
| [Show a few, it sorts the rest](sort-from-a-handful/) | Sorts new items into labels from about five examples per label and sends the ones it is unsure about to a person. | Recruiters, admissions offices, open source maintainers | Few-shot classification | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/sort-from-a-handful/walkthrough.ipynb) |
| [What are users really asking for?](what-people-ask-for/) | Groups a feedback export into named piles and similar groups, and counts how often each ask repeats. | Product managers, product owners, support leads | Clustering and near-duplicate grouping | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/cookbooks/blob/main/what-people-ask-for/walkthrough.ipynb) |

## The model

`harims95/hobbylm-embed-140m`: 140M total parameters, 36M active (excluding embeddings), 512-dimensional vectors, English. See [AGENTS.md](AGENTS.md) for load settings and tested thresholds, and each folder's README for its quickstart.

## License

[Apache-2.0](LICENSE)
