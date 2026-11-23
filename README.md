# HobbyLM-Embed cookbooks

Four small cookbooks for the [HobbyLM-Embed](https://huggingface.co/harims95/hobbylm-embed-140m) embedding model. Each folder holds a script, sample data and a walkthrough notebook. Everything runs locally on CPU. Embeddings only, no LLM.

## The cookbooks

- [what-changed](what-changed/)
  Compares two versions of a document clause by clause and reports only the changes that altered meaning.

  [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/hobbylm-embed-cookbook/blob/main/what-changed/walkthrough.ipynb)

- [show-me-where](show-me-where/)
  Checks an answer against your own documents and points to the section that backs it up, or says the answer is not there.

  [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/hobbylm-embed-cookbook/blob/main/show-me-where/walkthrough.ipynb)

- [sort-from-a-handful](sort-from-a-handful/)
  Sorts new items into labels from about five examples per label and sends the ones it is unsure about to a person.

  [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/hobbylm-embed-cookbook/blob/main/sort-from-a-handful/walkthrough.ipynb)

- [what-people-ask-for](what-people-ask-for/)
  Groups a feedback export into named piles and similar groups so you can see what people ask for.

  [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fuellabs-ai/hobbylm-embed-cookbook/blob/main/what-people-ask-for/walkthrough.ipynb)

## The model

`harims95/hobbylm-embed-140m`: 140M total parameters, 36M active (excluding embeddings), 512-dimensional vectors, English. See [AGENTS.md](AGENTS.md) for load settings and tested thresholds, and each folder's README for its quickstart.

## License

[Apache-2.0](LICENSE)
