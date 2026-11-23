# Sample data

Fictional sample data for a made-up company's internal help wiki. Every question,
passage and policy number here is invented. Nothing refers to a real company or person.

- `train_pairs.csv`: 100 (query, passage) pairs used for fine-tuning.
- `test_pairs.csv`: 20 held-out (query, passage_id) pairs, never seen in training.
- `passages.csv`: the full retrieval corpus of 170 passages: the 100 train
  passages, the 20 held-out ones and 50 distractor passages on adjacent topics
  that answer none of the questions.

The questions are written the way employees actually ask (informal,
abbreviations, typos) while the wiki passages are formal.

To use your own data, replace the three files and keep the column names: the
trainer applies the model's `query` and `passage` prompts by column name.
Always compare the fine-tuned model against the base model on your own
held-out data before switching.
