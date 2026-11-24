"""--sql-check test: 4 equivalent query pairs, plus a different-rows control.

Each pair rewrites the same query (BETWEEN vs two comparisons, IN vs an OR
chain, explicit JOIN vs a comma join, double negation). --code labels every
pair Changed because the text differs; --sql-check should report "same rows"
for each, and "different rows" for the control, where the rewrite really
does change the result.

Run from the what-changed directory:

    python tests/test_sql_check.py
"""
import csv
import pathlib
import sqlite3
import sys
import tempfile
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from what_changed import (DEFAULT_FLOOR, DEFAULT_THRESHOLD, MODEL_ID,
                          MODEL_REVISION, check_sql_pair, compare)


def build_db():
    schema = (pathlib.Path(__file__).parent / "fixtures"
              / "sql_check_schema.sql").read_text(encoding="utf-8")
    path = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path.close()
    conn = sqlite3.connect(path.name)
    conn.executescript(schema)
    conn.commit()
    return conn


def main():
    conn = build_db()

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION,
                                trust_remote_code=True)

    csv_path = pathlib.Path(__file__).parent / "fixtures" / "sql_equivalence_pairs.csv"
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    assert len(rows) == 4, f"expected 4 equivalence pairs, found {len(rows)}"

    failures = []
    for k, row in enumerate(rows, 1):
        pairs = compare(row["old"], row["new"], model, DEFAULT_THRESHOLD,
                        DEFAULT_FLOOR, code_mode=True)
        matched = [p for p in pairs if p.old and p.new]
        # --sql-check in the CLI runs on matched pairs; run it on the raw
        # texts too so the equivalence verdict is tested either way.
        verdict = check_sql_pair(conn, row["old"], row["new"])
        if matched:
            pair = matched[0]
            print(f"{k}. {pair.label}, sim {pair.sim:.2f}")
            print(f"   old: {row['old']}")
            print(f"   new: {row['new']}")
            print(f"   sql: {verdict}")
        else:
            labels = Counter(p.label for p in pairs)
            print(f"{k}. not matched by the embedding matcher ({dict(labels)}): "
                  f"the rewrite scores below the 0.74 floor, so the CLI would "
                  f"not reach --sql-check for this pair")
            print(f"   old: {row['old']}")
            print(f"   new: {row['new']}")
            print(f"   sql: {verdict} (run directly)")
        if verdict != row["expected"] and not verdict.startswith(row["expected"] + " ("):
            failures.append(f"pair {k}: expected {row['expected']!r}, got {verdict!r}")

    control_old = "SELECT * FROM users WHERE status = 'active';"
    control_new = "SELECT * FROM users WHERE status = 'inactive';"
    verdict = check_sql_pair(conn, control_old, control_new)
    print(f"5. [control] different-rows pair")
    print(f"   old: {control_old}")
    print(f"   new: {control_new}")
    print(f"   sql: {verdict}")
    if not (verdict or "").startswith("different rows"):
        failures.append(f"control: expected different rows, got {verdict!r}")

    conn.close()
    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: all 4 equivalence pairs report same rows; control reports different rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
