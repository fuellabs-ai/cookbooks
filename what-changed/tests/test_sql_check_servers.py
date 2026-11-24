"""--sql-check against real PostgreSQL and MySQL test databases.

Reuses the same fixture pairs as the SQLite test (4 SELECT equivalence
pairs, the SELECT control, 5 write pairs) and expects the same verdicts.
Per engine:

    python tests/seed_postgres.py          # needs HOBBYLM_PG_URL
    python tests/seed_mysql.py             # needs HOBBYLM_MYSQL_URL
    python tests/test_sql_check_servers.py

An engine is SKIPPED with a clear message when its environment variable
(HOBBYLM_PG_URL / HOBBYLM_MYSQL_URL) is not set or its server is not
reachable. After the checks the seed data on the server is verified
unchanged: row counts, a checksum query, and the full users table.
"""
import csv
import hashlib
import os
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from what_changed import (DEFAULT_FLOOR, DEFAULT_THRESHOLD, MODEL_ID,
                          MODEL_REVISION, check_sql_pair, compare)

EXPECTED_USERS = [
    (1, "Ada Lovelace", "ada@example.com", "active", 36),
    (2, "Grace Hopper", "grace@example.com", "active", 45),
    (3, "Edsger Dijkstra", None, "pending", 20),
    (4, "Donald Knuth", "knuth@example.com", "inactive", 17),
    (5, "Barbara Liskov", "liskov@example.com", "pending", 19),
]
EXPECTED_ORDER_COUNT = 6

CHECKSUMS = {
    "postgres": {
        "users": "SELECT md5(string_agg(id::text || '|' || name || '|' || "
                 "coalesce(email, '') || '|' || status || '|' || age::text, "
                 "'|' ORDER BY id)) FROM users",
        "orders": "SELECT md5(string_agg(id::text || '|' || user_id::text "
                  "|| '|' || total::text, '|' ORDER BY id)) FROM orders",
    },
    "mysql": {
        # MySQL 26.x has removed the md5() function; SHA2 is the equivalent.
        "users": "SELECT sha2(group_concat(id, '|', name, '|', "
                 "coalesce(email, ''), '|', status, '|', age ORDER BY id), 256) "
                 "FROM users",
        "orders": "SELECT sha2(group_concat(id, '|', user_id, '|', total "
                  "ORDER BY id), 256) FROM orders",
    },
}

ENGINES = [
    ("PostgreSQL", "HOBBYLM_PG_URL", "postgres", "tests/seed_postgres.py"),
    ("MySQL", "HOBBYLM_MYSQL_URL", "mysql", "tests/seed_mysql.py"),
]


def snapshot_state(conn, dialect):
    """Row counts, checksums and the full users table, for the final check."""
    cursor = conn.cursor()
    state = {}
    for table in ("users", "orders"):
        cursor.execute(f"SELECT count(*) FROM {table}")
        state[f"{table} count"] = cursor.fetchone()[0]
        cursor.execute(CHECKSUMS[dialect][table])
        state[f"{table} checksum"] = cursor.fetchone()[0]
    cursor.execute("SELECT id, name, email, status, age FROM users ORDER BY id")
    state["users rows"] = cursor.fetchall()
    return state


def run_engine(name, env_var, dialect, seed_hint, rows, model):
    url = os.environ.get(env_var)
    if not url:
        print(f"\n{name}: SKIPPED - set {env_var} to a test database URL "
              f"and seed it with {seed_hint}")
        return None
    from what_changed import connect_sql_check
    conn, resolved = connect_sql_check(url)
    if conn is None:
        print(f"\n{name}: SKIPPED - the connection could not be opened "
              "(see the message above)")
        return None
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT count(*) FROM users")
            cursor.fetchone()
        except Exception:
            print(f"\n{name}: SKIPPED - the tables are not seeded, run "
                  f"{seed_hint}")
            return None

        before = snapshot_state(conn, dialect)
        failures = []
        for k, row in enumerate(rows, 1):
            pairs = compare(row["old"], row["new"], model, DEFAULT_THRESHOLD,
                            DEFAULT_FLOOR, code_mode=True)
            matched = [p for p in pairs if p.old and p.new]
            verdict = check_sql_pair(conn, row["old"], row["new"], dialect)
            ok = (verdict or "").startswith(row["expected"] + " (") \
                or verdict == row["expected"]
            matched_text = (f"matched, sim {matched[0].sim:.2f}"
                            if matched else "not matched by the embedding matcher")
            print(f"{k}. [{'ok  ' if ok else 'MISS'}] {matched_text}")
            print(f"   old: {row['old']}")
            print(f"   new: {row['new']}")
            print(f"   sql: {verdict}")
            if not ok:
                failures.append(f"pair {k}: expected {row['expected']!r}, got {verdict!r}")

        after = snapshot_state(conn, dialect)
        if after["users rows"] != EXPECTED_USERS:
            for got, want in zip(after["users rows"], EXPECTED_USERS):
                if got != want:
                    failures.append(f"users row drifted: {got!r} != {want!r}")
        if after["users count"] != len(EXPECTED_USERS) \
                or after["orders count"] != EXPECTED_ORDER_COUNT:
            failures.append("row counts no longer match the seed data")
        if before != after:
            failures.append("the seed data changed during the checks: "
                            f"{ {k: v for k, v in before.items() if before[k] != after[k]} }")
        else:
            print(f"seed data unchanged: "
                  f"{', '.join(f'{k}: {v}' for k, v in after.items() if k.endswith('count'))}, "
                  f"checksums match, users rows match the seed")
        if failures:
            print(f"{name}: FAIL")
            for f in failures:
                print(f"  - {f}")
            return False
        print(f"{name}: PASS")
        return True
    finally:
        conn.close()


def main():
    csv_path = pathlib.Path(__file__).parent / "fixtures" / "sql_equivalence_pairs.csv"
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION,
                                trust_remote_code=True)

    results = {}
    for name, env_var, dialect, seed_hint in ENGINES:
        results[name] = run_engine(name, env_var, dialect, seed_hint, rows, model)

    if all(r is None for r in results.values()):
        print("\nno server was reachable: every engine test was skipped. "
              "The SQLite tests (tests/test_sql_check.py) pass without one.")
        return 0
    if any(r is False for r in results.values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
