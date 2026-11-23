#!/usr/bin/env python3
"""Group a pile of requests and show what repeats.

Embeddings only. No LLM. The model is HobbyLM-Embed 140M loaded through
Sentence Transformers with trust_remote_code=True. Requests are embedded as
plain text with no prompt_name, because clustering needs no query/passage
distinction. Vectors are unit length, so dot product is cosine similarity.

Usage:
    python piles.py requests.csv --column text [--piles piles.yaml]

What it does:
1. Reads a CSV, picks the text column, drops empty and exact-duplicate rows.
2. Optionally reads piles.yaml: user-named piles with 2-5 example requests
   each. Requests close enough to a pile go into it.
3. Everything left is clustered into groups. Each group gets a keyword label
   from TF-IDF (e.g. "export, csv, excel"). Labels are keywords, not
   summaries. Groups smaller than --min-group go to "Doesn't fit any group".
4. Every request lands in exactly one card: a named pile, a group, or
   "Doesn't fit any group". Near-duplicate wording shows up as a "said again"
   breakdown inside each card: how people put the same ask again, with a
   count each.
5. Writes report.html and groups.csv (request, group, score).

Settings defaults come from calibrate.py runs on the labelled samples.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path
from typing import Sequence

import numpy as np

DEFAULT_MODEL = "harims95/hobbylm-embed-140m"
MODEL_REVISION = "ea708cee"
DEFAULT_DEDUP_SIM = 0.92
DEFAULT_CLUSTER_SIM = 0.75
DEFAULT_MIN_GROUP = 3
DEFAULT_PILE_SIM = 0.75
COLUMN_HINTS = [
    "text", "request", "message", "body", "comment", "feedback",
    "review", "proposal", "abstract", "description", "content", "notes",
]
MAX_EMBED_WORDS = 200
DOES_NOT_FIT = "Doesn't fit any group"
NO_FIT_KEY = "doesn't fit"


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def read_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]
    if not rows:
        raise ValueError(f"No rows in {csv_path}")
    return rows


def pick_column(rows: Sequence[dict], column: str | None) -> str:
    available = list(rows[0].keys())
    if column:
        if column not in available:
            raise ValueError(
                f"Column '{column}' is not in the file. Available: {', '.join(available)}"
            )
        return column
    lowered = {name.lower(): name for name in available}
    for hint in COLUMN_HINTS:
        if hint in lowered:
            return lowered[hint]
    raise ValueError(
        "Could not guess the text column. Available: "
        f"{', '.join(available)}. Use --column."
    )


def _dedup_key(text: str) -> str:
    return " ".join(text.split()).casefold()


def clean_requests(rows: Sequence[dict], column: str) -> tuple[list[str], dict]:
    """Keep non-empty texts, drop exact duplicates (case and spacing ignored)."""
    stats = {
        "rows_read": len(rows),
        "empty_dropped": 0,
        "exact_duplicates_dropped": 0,
    }
    texts: list[str] = []
    seen: set[str] = set()
    for row in rows:
        text = " ".join(str(row.get(column) or "").split())
        if not text:
            stats["empty_dropped"] += 1
            continue
        key = _dedup_key(text)
        if key in seen:
            stats["exact_duplicates_dropped"] += 1
            continue
        seen.add(key)
        texts.append(text)
    stats["grouped"] = len(texts)
    return texts, stats


# ---------------------------------------------------------------------------
# Model and structure
# ---------------------------------------------------------------------------


def load_model(model_name: str = DEFAULT_MODEL):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, revision=MODEL_REVISION,
                               trust_remote_code=True)


def embed(texts: Sequence[str], model, batch_size: int = 64) -> np.ndarray:
    capped = [" ".join(t.split()[:MAX_EMBED_WORDS]) for t in texts]
    vectors = model.encode(
        capped, batch_size=batch_size, show_progress_bar=False,
        convert_to_numpy=True,
    )
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-9)


def _cluster(similarities: np.ndarray, sim_threshold: float, linkage: str) -> np.ndarray:
    """Agglomerative clustering on a precomputed similarity matrix."""
    from sklearn.cluster import AgglomerativeClustering

    n = similarities.shape[0]
    if n == 1:
        return np.array([0])
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1.0 - sim_threshold,
        metric="precomputed",
        linkage=linkage,
    )
    return clustering.fit_predict(1.0 - similarities)


def _centroid(vectors: np.ndarray, members: Sequence[int]) -> np.ndarray:
    centre = vectors[list(members)].mean(axis=0)
    return centre / max(np.linalg.norm(centre), 1e-9)


def parse_piles(path: Path) -> dict[str, list[str]]:
    """Parse the simple piles format: a name, then '- example' lines."""
    piles: dict[str, list[str]] = {}
    name: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t", "-")):
            if name is None:
                raise ValueError(f"{path}: example line before any pile name: {line!r}")
            item = line.strip()
            if not item.startswith("-"):
                raise ValueError(f"{path}: expected '- example' under {name!r}: {line!r}")
            example = item[1:].strip()
            if example:
                piles[name].append(example)
        else:
            name = line.rstrip(":").strip()
            piles.setdefault(name, [])
    bad = [n for n, e in piles.items() if not 2 <= len(e) <= 5]
    if bad:
        raise ValueError(
            f"{path}: piles need 2-5 examples each, these do not: {', '.join(bad)}"
        )
    if not piles:
        raise ValueError(f"{path}: no piles found")
    return piles


def assign_piles(
    vectors: np.ndarray,
    pile_blocks: dict[str, np.ndarray],
    pile_sim: float,
) -> tuple[dict[int, str], np.ndarray]:
    """Return {index: pile name} for requests close enough to a pile.

    A pile's score for a request is the mean similarity to its 2-5 examples,
    which is stricter than a centroid and keeps small piles selective.
    """
    if not pile_blocks:
        return {}, np.zeros(vectors.shape[0], dtype=np.float32)
    names = list(pile_blocks)
    scores = np.stack(
        [(vectors @ pile_blocks[name].T).mean(axis=1) for name in names], axis=1
    )
    best = scores.argmax(axis=1)
    best_score = scores[np.arange(len(scores)), best]
    assignment = {
        int(i): names[int(best[i])]
        for i in range(len(scores))
        if best_score[i] >= pile_sim
    }
    return assignment, best_score


def segment(
    vectors: np.ndarray,
    dedup_sim: float = DEFAULT_DEDUP_SIM,
    cluster_sim: float = DEFAULT_CLUSTER_SIM,
    min_group: int = DEFAULT_MIN_GROUP,
    pile_sim: float = DEFAULT_PILE_SIM,
    piles: dict[str, list[str]] | None = None,
    model=None,
) -> dict:
    """Run the whole structural pipeline on unit-norm vectors.

    Returns a dict with:
      said_again: list of dicts (members, count, example) sorted by count.
        This is a breakdown view only: its members also belong to a pile,
        a group or Doesn't fit any group, and the report shows the cluster
        inside that card.
      pile_of: {index: pile name}
      cluster_of: {index: cluster id}
      leftover: indices that still need clustering
      doesn_fit: list of indices
    """
    n = vectors.shape[0]
    sims = vectors @ vectors.T

    # 1. near-duplicate wording: complete linkage, so every member of a
    #    cluster is very similar to every other member. These clusters are
    #    only a breakdown; they do not claim rows.
    dedup_labels = _cluster(sims, dedup_sim, "complete")
    said_again = []
    for label in sorted(set(dedup_labels)):
        members = [int(i) for i in np.where(dedup_labels == label)[0]]
        if len(members) < 2:
            continue
        centre = _centroid(vectors, members)
        example = max(members, key=lambda i: float(vectors[i] @ centre))
        said_again.append(
            {"members": members, "count": len(members), "example": int(example)}
        )
    said_again.sort(key=lambda c: -c["count"])

    # 2. user piles
    pile_blocks: dict[str, np.ndarray] = {}
    if piles:
        if model is None:
            raise ValueError("assigning piles needs the model to embed examples")
        pile_vectors = embed(
            [example for examples in piles.values() for example in examples], model
        )
        cursor = 0
        for name, examples in piles.items():
            pile_blocks[name] = pile_vectors[cursor : cursor + len(examples)]
            cursor += len(examples)
    pile_of, pile_scores = assign_piles(vectors, pile_blocks, pile_sim)
    claimed = set(pile_of)

    # 3. cluster whatever is left
    leftover = [i for i in range(n) if i not in claimed]
    cluster_of: dict[int, int] = {}
    if leftover:
        sub = vectors[leftover]
        sub_sims = sub @ sub.T
        sub_labels = _cluster(sub_sims, cluster_sim, "average")
        for position, index in enumerate(leftover):
            cluster_of[index] = int(sub_labels[position])

    cluster_counts: dict[int, int] = {}
    for label in cluster_of.values():
        cluster_counts[label] = cluster_counts.get(label, 0) + 1
    small_of = {i: label for i, label in cluster_of.items() if cluster_counts[label] < min_group}
    doesn_fit = sorted(small_of)
    cluster_of = {i: label for i, label in cluster_of.items() if i not in small_of}

    return {
        "said_again": said_again,
        "pile_of": pile_of,
        "pile_scores": pile_scores,
        "cluster_of": cluster_of,
        "small_of": small_of,
        "doesn_fit": doesn_fit,
    }


# ---------------------------------------------------------------------------
# Keyword labels
# ---------------------------------------------------------------------------


def keyword_label(texts: Sequence[str], width: int = 3) -> str:
    """Top TF-IDF keywords for a group of texts. Keywords, not a summary."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    if not texts:
        return ""
    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        matrix = vectorizer.fit_transform(texts)
        scores = np.asarray(matrix.mean(axis=0)).ravel()
        terms = vectorizer.get_feature_names_out()
        order = scores.argsort()[::-1][:width]
        return ", ".join(terms[i] for i in order if scores[i] > 0)
    except ValueError:  # empty vocabulary after stop words
        words: dict[str, int] = {}
        for text in texts:
            for word in text.split():
                key = word.casefold()
                words[key] = words.get(key, 0) + 1
        top = sorted(words, key=words.get, reverse=True)[:width]
        return ", ".join(top)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def diverse_quotes(
    vectors: np.ndarray, members: Sequence[int], k: int = 3
) -> list[int]:
    """The k most different requests in a card.

    Starts from the member closest to the card centroid, then repeatedly adds
    the member least similar to everything picked so far. Each quote is the
    one furthest from the quotes already chosen, so the reader sees the same
    ask in different words.
    """
    members = list(members)
    if len(members) <= k:
        return members
    centre = _centroid(vectors, members)
    picked = [max(members, key=lambda i: float(vectors[i] @ centre))]
    while len(picked) < k:
        best = min(
            (i for i in members if i not in picked),
            key=lambda i: max(float(vectors[i] @ vectors[p]) for p in picked),
        )
        picked.append(best)
    return picked


def _said_again_breakdown(
    texts: Sequence[str],
    vectors: np.ndarray,
    card_members: set[int],
    said_again: Sequence[dict],
    max_lines: int = 5,
) -> list[dict]:
    """Said-again clusters inside one card: how people put the same ask again."""
    by_index: dict[int, dict] = {}
    for cluster in said_again:
        for index in cluster["members"]:
            by_index[int(index)] = cluster
    groups: dict[int, list[int]] = {}
    for index in sorted(card_members):
        cluster = by_index.get(index)
        if cluster is None:
            continue
        groups.setdefault(id(cluster), []).append(index)
    lines: list[dict] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        centre = _centroid(vectors, members)
        example = max(members, key=lambda i: float(vectors[i] @ centre))
        lines.append({"count": len(members), "example": int(example)})
    lines.sort(key=lambda line: -line["count"])
    return lines[:max_lines]


def build_groups(texts: Sequence[str], vectors: np.ndarray, result: dict) -> list[dict]:
    """Turn a segmentation into a sorted list of group dicts for output.

    Every request lands in exactly one card: a pile, a group, or Doesn't fit
    any group. Said-again wording shows up as a breakdown inside each card.
    """
    groups: list[dict] = []

    pile_members: dict[str, list[int]] = {}
    for index, name in result["pile_of"].items():
        pile_members.setdefault(name, []).append(int(index))
    for name, members in pile_members.items():
        centre = _centroid(vectors, members)
        scores = {i: float(result["pile_scores"][i]) for i in members}
        groups.append(
            {
                "kind": "pile",
                "name": name,
                "sort_name": name.casefold(),
                "members": sorted(members, key=lambda i: -scores[i]),
                "scores": scores,
                "label": None,
                "example": texts[max(scores, key=scores.get)],
                "breakdown": _said_again_breakdown(
                    texts, vectors, set(members), result["said_again"]
                ),
                "quotes": diverse_quotes(vectors, members),
            }
        )

    cluster_members: dict[int, list[int]] = {}
    for index, label in result["cluster_of"].items():
        cluster_members.setdefault(label, []).append(int(index))
    used = {g["name"] for g in groups}
    for label, members in cluster_members.items():
        centre = _centroid(vectors, members)
        member_texts = [texts[i] for i in members]
        label_text = keyword_label(member_texts) or "mixed wording"
        name = label_text
        suffix = 2
        while name in used:
            name = f"{label_text} ({suffix})"
            suffix += 1
        used.add(name)
        scores = {i: float(vectors[i] @ centre) for i in members}
        groups.append(
            {
                "kind": "group",
                "name": name,
                "sort_name": (-len(members), name),
                "members": sorted(members, key=lambda i: -scores[i]),
                "scores": scores,
                "label": label_text,
                "example": texts[max(scores, key=scores.get)],
                "breakdown": _said_again_breakdown(
                    texts, vectors, set(members), result["said_again"]
                ),
                "quotes": diverse_quotes(vectors, members),
            }
        )

    if result["doesn_fit"]:
        subclusters: list[tuple[int, str]] = []
        by_small: dict[int, list[int]] = {}
        for index, cluster_id in result["small_of"].items():
            by_small.setdefault(cluster_id, []).append(int(index))
        for members_small in by_small.values():
            if len(members_small) < 2:
                continue
            centre_small = _centroid(vectors, members_small)
            best = max(members_small, key=lambda i: float(vectors[i] @ centre_small))
            subclusters.append((len(members_small), texts[best]))
        subclusters.sort(key=lambda item: -item[0])
        members_all = list(result["doesn_fit"])
        groups.append(
            {
                "kind": "doesn't fit",
                "name": DOES_NOT_FIT,
                "sort_name": "zzz0",
                "members": members_all,
                "scores": {i: 0.0 for i in members_all},
                "label": None,
                "example": None,
                "breakdown": _said_again_breakdown(
                    texts, vectors, set(members_all), result["said_again"]
                ),
                "quotes": diverse_quotes(vectors, members_all) if len(members_all) >= 2 else [],
                "subclusters": subclusters,
            }
        )

    cards_first = {"pile": 0, "group": 1, "doesn't fit": 2}
    groups.sort(key=lambda g: (cards_first[g["kind"]], g["sort_name"]))
    return groups


def summarize_counts(stats: dict, groups: Sequence[dict]) -> dict:
    """Count the cards and check that every grouped row is counted exactly once.

    Raises ValueError if the parts do not add up to the grouped rows.
    """
    parts = {
        "pile": sum(len(g["members"]) for g in groups if g["kind"] == "pile"),
        "group": sum(len(g["members"]) for g in groups if g["kind"] == "group"),
        "doesn't fit": sum(
            len(g["members"]) for g in groups if g["kind"] == "doesn't fit"
        ),
    }
    total = parts["pile"] + parts["group"] + parts["doesn't fit"]
    if total != stats["grouped"]:
        n_piles, n_groups, n_doesnt = parts["pile"], parts["group"], parts["doesn't fit"]
        raise ValueError(
            "count check failed: "
            f"{n_piles} in piles + {n_groups} in groups + "
            f"{n_doesnt} that don't fit = {total}, "
            f"but {stats['grouped']} rows were grouped"
        )
    parts["pile_cards"] = sum(1 for g in groups if g["kind"] == "pile")
    parts["group_cards"] = sum(1 for g in groups if g["kind"] == "group")
    return parts


def write_groups_csv(path: Path, texts: Sequence[str], groups: Sequence[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["request", "group", "score"])
        for group in groups:
            for index in group["members"]:
                writer.writerow(
                    [texts[index], group["name"], f"{group['scores'][index]:.3f}"]
                )


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def build_report_html(
    csv_name: str,
    stats: dict,
    texts: Sequence[str],
    groups: Sequence[dict],
    has_piles: bool,
) -> str:
    parts_counts = summarize_counts(stats, groups)
    grouped = stats["grouped"]

    parts: list[str] = []
    parts.append(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>What people ask for</title><style>"
        "body{font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;"
        "max-width:760px;margin:24px auto;padding:0 16px;color:#1a1a24;}"
        "h1{font-size:22px;margin:0 0 4px;} h2{font-size:16px;margin:28px 0 8px;"
        "border-bottom:1px solid #ddd;padding-bottom:4px;}"
        ".stats{color:#555;font-size:13px;line-height:1.5;}"
        ".group{border:1px solid #ddd;border-radius:8px;padding:10px 14px;margin:10px 0;}"
        ".count{font-weight:600;} .label{color:#444;}"
        "details{margin-top:6px;} summary{cursor:pointer;color:#0645ad;font-size:13px;}"
        "li{margin:3px 0;font-size:14px;} ul{padding-left:20px;margin:6px 0;}"
        "ul.compact li{font-size:13px;color:#3a3a48;}"
        "footer{color:#777;font-size:12px;margin-top:28px;}"
        "</style></head><body>"
    )
    parts.append(f"<h1>What people ask for: {_esc(csv_name)}</h1>")
    parts.append(
        f"<p class='stats'>{stats['rows_read']} rows read, "
        f"{stats['empty_dropped']} empty dropped, "
        f"{stats['exact_duplicates_dropped']} exact duplicates dropped.</p>"
    )

    # Top requests: the top 10 cards by count, copyable into a planning doc.
    cards = [g for g in groups if g["kind"] in {"pile", "group"}]
    cards.sort(key=lambda g: (-len(g["members"]), str(g["name"]).casefold()))
    top = cards[:10]
    parts.append("<h2>Top requests</h2>")
    parts.append("<ul>")
    for card in top:
        count = len(card["members"])
        share = round(count * 100 / grouped)
        title = card["name"] if card["kind"] == "pile" else (
            f"{card['name']} (keywords)"
        )
        parts.append(
            f"<li>{_esc(title)}: {count} requests ({share}% of {grouped})</li>"
        )
    parts.append("</ul>")

    # Summary line: every grouped row is in exactly one bucket.
    summary = f"{grouped} requests: "
    bucket_bits = []
    if has_piles:
        bucket_bits.append(
            f"{parts_counts['pile']} in {parts_counts['pile_cards']} named piles"
        )
    bucket_bits.append(
        f"{parts_counts['group']} in {parts_counts['group_cards']} groups"
    )
    bucket_bits.append(
        f"{parts_counts[NO_FIT_KEY]} don't fit any group"
    )
    summary += ", ".join(bucket_bits) + "."
    parts.append(f"<p class='stats'>{summary}</p>")

    for kind, heading in (
        ("pile", "Named piles"),
        ("group", "Groups"),
        ("doesn't fit", "Doesn't fit any group"),
    ):
        section = [g for g in groups if g["kind"] == kind]
        if not section:
            continue
        parts.append(f"<h2>{heading}</h2>")
        if kind == "group":
            parts.append(
                "<p class='stats'>Group names are the top TF-IDF keywords for the "
                "group, not summaries. Rename groups in piles.yaml and rerun if you "
                "have better names.</p>"
            )
        for group in section:
            members = group["members"]
            count = len(members)
            parts.append("<div class='group'>")
            if kind == "pile":
                parts.append(f"<p class='count'>{_esc(group['name'])}: {count} requests</p>")
            elif kind == "group":
                parts.append(f"<p class='count'>{count} requests</p>")
                parts.append(
                    f"<p class='label'>Keywords: {_esc(group['label'])}</p>"
                )
            else:
                parts.append(
                    f"<p class='count'>{count} requests unlike the rest of the file. "
                    "Unlike the rest does not mean new or important.</p>"
                )
            breakdown = group.get("breakdown") or []
            if breakdown:
                lines = "".join(
                    f"<li>{line['count']} said it this way: "
                    f"&quot;{_esc(texts[line['example']])}&quot;</li>"
                    for line in breakdown
                )
                parts.append(
                    "<p class='stats'>How the wording repeats:</p>"
                    f"<ul class='compact'>{lines}</ul>"
                )
            if kind == "doesn't fit":
                sub_lines = "".join(
                    f"<li>{count_small} requests: {_esc(example)}</li>"
                    for count_small, example in group.get("subclusters", [])
                )
                singles = [
                    texts[i]
                    for i in members
                    if not any(
                        example == texts[i]
                        for _c, example in group.get("subclusters", [])
                    )
                ]
                single_lines = "".join(f"<li>{_esc(t)}</li>" for t in singles)
                parts.append(f"<ul>{sub_lines}{single_lines}</ul>")
            else:
                parts.append(
                    "<p class='stats'>3 requests from this card, picked to differ "
                    "from each other:</p><ul>"
                )
                for index in group.get("quotes") or members[:3]:
                    parts.append(f"<li>{_esc(texts[index])}</li>")
                parts.append("</ul>")
            rest = [i for i in members if i not in set(group.get("quotes") or [])]
            if kind != "doesn't fit" and rest:
                items = "".join(f"<li>{_esc(texts[i])}</li>" for i in rest)
                word = "other request" if len(rest) == 1 else "other requests"
                parts.append(
                    f"<details><summary>Show {len(rest)} {word}</summary><ul>{items}</ul></details>"
                )
            parts.append("</div>")

    parts.append(
        "<footer>Made locally with HobbyLM-Embed 140M. Counts are how many "
        "requests repeat, not how important they are. Groups are similar "
        "wording and meaning, not importance or truth.</footer>"
    )
    parts.append("</body></html>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(
    csv_path: Path,
    column: str | None,
    piles_path: Path | None,
    dedup_sim: float,
    cluster_sim: float,
    min_group: int,
    pile_sim: float,
    model_name: str,
    report_path: Path | None,
    csv_out_path: Path | None,
    quiet: bool = False,
) -> tuple[list[dict], list[str], dict]:
    rows = read_rows(csv_path)
    column = pick_column(rows, column)
    texts, stats = clean_requests(rows, column)
    if len(texts) < 2:
        raise ValueError("Not enough non-empty requests to group.")

    model = load_model(model_name)
    vectors = embed(texts, model)
    piles = parse_piles(piles_path) if piles_path else None
    result = segment(
        vectors,
        dedup_sim=dedup_sim,
        cluster_sim=cluster_sim,
        min_group=min_group,
        pile_sim=pile_sim,
        piles=piles,
        model=model,
    )
    groups = build_groups(texts, vectors, result)
    parts_counts = summarize_counts(stats, groups)

    if report_path:
        report_path.write_text(
            build_report_html(csv_path.name, stats, texts, groups, piles is not None),
            encoding="utf-8",
        )
    if csv_out_path:
        write_groups_csv(csv_out_path, texts, groups)

    if not quiet:
        print(
            f"{stats['rows_read']} rows read, "
            f"{stats['empty_dropped']} empty dropped, "
            f"{stats['exact_duplicates_dropped']} exact duplicates dropped"
        )
        summary = f"{stats['grouped']} requests: "
        bits = []
        if parts_counts["pile_cards"]:
            bits.append(
                f"{parts_counts['pile']} in {parts_counts['pile_cards']} named piles"
            )
        bits.append(f"{parts_counts['group']} in {parts_counts['group_cards']} groups")
        bits.append(f"{parts_counts[NO_FIT_KEY]} don't fit any group")
        print(summary + ", ".join(bits))
        for group in groups:
            if group["kind"] == "pile":
                print(f"  pile '{group['name']}': {len(group['members'])} requests")
            elif group["kind"] == "group":
                print(f"  group '{group['name']}': {len(group['members'])} requests")
        for group in groups:
            if group["kind"] == NO_FIT_KEY:
                print(f"  {group['name']}: {len(group['members'])} requests")
        if report_path:
            print(f"wrote {report_path}")
        if csv_out_path:
            print(f"wrote {csv_out_path}")
    return groups, texts, stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Group requests and show what repeats."
    )
    parser.add_argument("csv_file", help="CSV file with one request per row")
    parser.add_argument("--column", default=None, help="Text column to read")
    parser.add_argument("--piles", default=None, help="piles.yaml with named piles")
    parser.add_argument(
        "--dedup-sim", type=float, default=DEFAULT_DEDUP_SIM,
        help=f"Similarity above which wording counts as said again in a card's breakdown (default {DEFAULT_DEDUP_SIM})",
    )
    parser.add_argument(
        "--cluster-sim", type=float, default=DEFAULT_CLUSTER_SIM,
        help=f"Similarity below which requests split into different groups (default {DEFAULT_CLUSTER_SIM})",
    )
    parser.add_argument(
        "--min-group", type=int, default=DEFAULT_MIN_GROUP,
        help=f"Groups smaller than this go to Doesn't fit any group (default {DEFAULT_MIN_GROUP})",
    )
    parser.add_argument(
        "--pile-sim", type=float, default=DEFAULT_PILE_SIM,
        help=f"Similarity to pile examples needed to join a pile (default {DEFAULT_PILE_SIM})",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Sentence Transformers model")
    parser.add_argument("--report", default="report.html", help="Report file (empty string disables)")
    parser.add_argument("--groups-csv", default="groups.csv", help="groups.csv file (empty string disables)")
    parser.add_argument("--json", action="store_true", help="Print a JSON summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    csv_path = Path(args.csv_file)
    piles_path = Path(args.piles) if args.piles else None
    # Defaults land next to the input CSV, which is where you look for them.
    report_path = (
        csv_path.parent / "report.html" if args.report == "report.html"
        else Path(args.report) if args.report
        else None
    )
    csv_out_path = (
        csv_path.parent / "groups.csv" if args.groups_csv == "groups.csv"
        else Path(args.groups_csv) if args.groups_csv
        else None
    )
    groups, texts, stats = run(
        Path(args.csv_file),
        args.column,
        piles_path,
        args.dedup_sim,
        args.cluster_sim,
        args.min_group,
        args.pile_sim,
        args.model,
        report_path,
        csv_out_path,
        quiet=args.json,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "file": args.csv_file,
                    "stats": stats,
                    "groups": [
                        {
                            "kind": g["kind"],
                            "name": g["name"],
                            "count": len(g["members"]),
                        }
                        for g in groups
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
