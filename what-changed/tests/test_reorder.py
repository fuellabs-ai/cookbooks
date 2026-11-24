"""Reorder test: shuffle a real Laravel config, rename 2 keys, change 2 values.

what-changed --code matches lines by content, not position, so a pure
reorder should not appear in the report at all, and a renamed key should
pair with its own old line as one Changed pair rather than showing up as
a removal plus an addition.

Run from the what-changed directory:

    python tests/test_reorder.py
"""
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from what_changed import (DEFAULT_FLOOR, DEFAULT_THRESHOLD, MODEL_ID,
                          MODEL_REVISION, compare)


def main():
    fixture = pathlib.Path(__file__).parent / "fixtures" / "laravel_database_v10.php"
    old_lines = fixture.read_text(encoding="utf-8").splitlines()
    old_lines = [line for line in old_lines if line.strip()]

    # Each of these appears exactly once in the fixture.
    renames = {
        "'unix_socket' => env('DB_SOCKET', '')":
            "'socket_path' => env('DB_SOCKET', '')",
        "'foreign_key_constraints' => env('DB_FOREIGN_KEYS', true)":
            "'enforce_foreign_keys' => env('DB_FOREIGN_KEYS', true)",
    }
    value_changes = {
        "'sslmode' => 'prefer'": "'sslmode' => 'require'",
        "'client' => env('REDIS_CLIENT', 'phpredis')":
            "'client' => env('REDIS_CLIENT', 'predis')",
    }

    new_lines = list(old_lines)
    replaced = 0
    for old_frag, new_frag in {**renames, **value_changes}.items():
        hits = [i for i, line in enumerate(new_lines) if old_frag in line]
        assert len(hits) == 1, f"fixture key not unique ({len(hits)}x): {old_frag}"
        new_lines[hits[0]] = new_lines[hits[0]].replace(old_frag, new_frag)
        replaced += 1
    assert replaced == 4

    random.seed(7)
    random.shuffle(new_lines)

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION,
                                trust_remote_code=True)

    pairs = compare("\n".join(old_lines), "\n".join(new_lines), model,
                    DEFAULT_THRESHOLD, DEFAULT_FLOOR, code_mode=True)

    from collections import Counter
    counts = Counter(p.label for p in pairs)
    changed = [p for p in pairs if p.label == "changed"]
    print(f"counts: {dict(counts)}")
    for p in changed:
        print(f"  changed [{p.reason}]")
        print(f"    old: {p.old}")
        print(f"    new: {p.new}")

    failures = []
    if counts["changed"] != 4:
        failures.append(f"expected exactly 4 Changed pairs, got {counts['changed']}")
    for label in ("added", "removed", "reworded"):
        if counts[label]:
            failures.append(f"expected no {label} pairs, got {counts[label]}")
    for old_frag, new_frag in renames.items():
        if not any(old_frag in (p.old or "") and new_frag in (p.new or "")
                   for p in changed):
            failures.append(f"renamed key not paired: {old_frag}")
    for old_frag, new_frag in value_changes.items():
        if not any(old_frag in (p.old or "") and new_frag in (p.new or "")
                   for p in changed):
            failures.append(f"value change not paired: {old_frag}")

    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: reorder is invisible, both renamed keys paired, exactly the 4 changes shown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
