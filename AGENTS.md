# Notes for coding agents

Work at the repo root. Do not edit the cookbook folders unless the task is clearly about one of them, and keep their measured numbers as they are unless you rerun the notebooks.

## Model

- Use `harims95/hobbylm-embed-140m` through Sentence Transformers, pinned to revision `ea708cee107818fa0c1871eebd26d82a1e3fb1aa`.
- Load it with `trust_remote_code=True`. The repo code defines the model itself; remote code is required.
- Prompts: for search and retrieval jobs, embed the question side with `prompt_name="query"` and the document side with `prompt_name="passage"`. The model adds the prefixes itself. Three of the four recipes here (what-changed, sort-from-a-handful, what-people-ask-for) are similarity or clustering jobs and embed plain text with no `prompt_name`; keep that behavior in those scripts.
- Sequence length defaults to 512 tokens and can be raised to 2,048.

## Model facts

- 140M total parameters, 36M active (excluding embeddings).
- 512-dimensional output vectors, unit-norm, so dot product is cosine similarity.
- English.
- Runs locally on CPU. Embeddings only, no LLM.

## Tested thresholds

These are the settings the cookbooks were measured with. Do not change them without rerunning the calibration and the notebooks.

- what-changed: reword threshold 0.85, related floor 0.74 (picked on the four sample pairs).
- show-me-where: upper cut-off 0.775, lower cut-off 0.680, calibrated on the labelled questions (the code defaults, before calibration, are 0.75 and 0.65).
- sort-from-a-handful: the margin is recommended by `calibrate.py` on dev items only and saved to `margin.json`; on the real issue dev set it came out at 0.010 with the centroid method. The code default, when no `margin.json` exists, is 0.05.
- what-people-ask-for: `dedup_sim` 0.92, `cluster_sim` 0.75, `pile_sim` 0.75, `min_group` 3.
