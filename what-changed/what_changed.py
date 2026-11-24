#!/usr/bin/env python3
"""What really changed? Compare two versions of a document by meaning.

A HobbyLM-Embed cookbook recipe. Embeddings only, no LLM.

    python what_changed.py old.txt new.txt [--code] [--ignore-format]
    [--sql-check DB_FILE_OR_URL] [--show-all] [--threshold 0.90]

With --code the two versions are read as code or config: one clause per line,
no sentence splitting, and any text change on a non-comment line is Changed.
In code there is no harmless rewording outside comments. --ignore-format
normalises quote style and whitespace before comparing, so lines that differ
only by formatting count as Unchanged. --sql-check accepts a SQLite file
path or a PostgreSQL/MySQL URL, and runs matched SQL pairs against it:
SELECTs are compared by the rows they return, UPDATE and DELETE by the
rows they change (on SQLite via a temporary copy, on a server inside a
rolled-back transaction). Non-local server hosts need --allow-remote-db.

Model: harims95/hobbylm-embed-140m via Sentence Transformers
(trust_remote_code=True). The model turns each clause into a normalized
512-dimensional vector, so similarity is a plain dot product.

This is a similarity job, not a search job: clauses are embedded as plain
text with no query/passage prompt prefixes.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sqlite3
import sys
import tempfile
from urllib.parse import urlsplit
from collections import Counter, defaultdict

import numpy as np

MODEL_ID = "harims95/hobbylm-embed-140m"
MODEL_REVISION = "ea708cee107818fa0c1871eebd26d82a1e3fb1aa"
DEFAULT_MAX_TOKENS = 512  # the model reads 512 tokens by default
MAX_TOKEN_LIMIT = 2048    # up to 2,048 if you raise the limit

DEFAULT_THRESHOLD = 0.85  # reworded vs changed; midpoint of the gap observed on examples/
DEFAULT_FLOOR = 0.74      # below this a clause has no close match at all

# Risky phrases. If one is added, removed or swapped inside a matched pair,
# the pair counts as Changed even when the similarity is high. Negation words
# collapse into one class so "no X" -> "without X" stays a rewording, while
# "not included" -> "included" does not.
DEFAULT_CLAIM_WORDS = [
    "may contain", "contains", "free", "guaranteed", "up to", "at least",
    "unlimited", "high in", "source of", "certified", "no longer",
    "not", "no", "without",
]
NEGATION_CLASS = {"not", "no", "no longer", "without"}

MONTHS = {
    "jan": "January", "feb": "February", "mar": "March", "apr": "April",
    "may": "May", "jun": "June", "jul": "July", "aug": "August",
    "sep": "September", "sept": "September", "oct": "October",
    "nov": "November", "dec": "December",
    "january": "January", "february": "February", "march": "March",
    "april": "April", "june": "June", "july": "July", "august": "August",
    "september": "September", "october": "October", "november": "November",
    "december": "December",
}
MONTH_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
PRICE_RE = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d+)?")
PERCENT_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s?%|\b\d[\d,]*(?:\.\d+)? percent\b", re.IGNORECASE)


def normalize(text: str) -> str:
    """Collapse whitespace for exact-match comparison."""
    return re.sub(r"\s+", " ", text).strip()


def split_clauses(text: str) -> list[str]:
    """Split a document into clauses: bullet lines and sentences.

    Keeps each clause short; the model reads 512 tokens by default, up to
    2,048 if you raise the limit, and short clauses match far better than
    long paragraphs.
    """
    clauses: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Strip markdown heading markers and bullet markers.
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^[-*•]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        if not line:
            continue
        # Sentence split: punctuation, whitespace, then a new capital or digit.
        pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9$(])", line)
        for piece in pieces:
            piece = normalize(piece)
            if piece:
                clauses.append(piece)
    return clauses


def split_lines(text: str) -> list[str]:
    """Code mode: one clause per line, no sentence splitting, blanks skipped."""
    return [line.strip() for line in text.splitlines() if line.strip()]


COMMENT_PREFIXES = ("//", "#", "--", "/*", "*", "*/", "|")


def is_comment(line: str) -> bool:
    """True for a comment line in code mode: starts with a comment marker.

    | covers the docblock-style comment boxes Laravel and similar PHP
    config files draw with vertical bars.
    """
    return line.strip().startswith(COMMENT_PREFIXES)


def format_normalize(text: str) -> str:
    """Whitespace collapsed and quote characters unified.

    Used by --ignore-format so 'x' and "x" compare equal.
    """
    return normalize(text).replace('"', "'")


def _diff_chunk(tokens: list[str]) -> str:
    """Join tokens for display, dropping a trailing clause punctuation mark."""
    text = " ".join(tokens)
    stripped = text.rstrip(",;:")
    return stripped if stripped else text


def token_diff(old_text: str, new_text: str) -> str | None:
    """Compact word-level summary of what differs between two lines.

    "...'debug' => false," vs "...'debug' => true," becomes "false -> true".
    """
    old_tokens = old_text.split()
    new_tokens = new_text.split()
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            a=old_tokens, b=new_tokens, autojunk=False).get_opcodes():
        if tag == "replace":
            parts.append(f"{_diff_chunk(old_tokens[i1:i2])} -> {_diff_chunk(new_tokens[j1:j2])}")
        elif tag == "delete":
            parts.append(f"{_diff_chunk(old_tokens[i1:i2])} -> (removed)")
        elif tag == "insert":
            parts.append(f"(added) -> {_diff_chunk(new_tokens[j1:j2])}")
    return "; ".join(parts) if parts else None


def extract_claims(text: str, claim_words=None) -> Counter:
    """Risky claim phrases in a clause, counted by phrase.

    Complements the number check: "high in fiber" and "good source of fiber"
    embed almost the same and carry no numbers, but swap a claim word.
    """
    if claim_words is None:
        claim_words = DEFAULT_CLAIM_WORDS
    t = text.lower()
    claims: Counter = Counter()
    for phrase in claim_words:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        n = len(re.findall(pattern, t))
        if n:
            key = "negation" if phrase in NEGATION_CLASS else phrase
            claims[key] += n
            t = re.sub(pattern, " ", t)
    return claims


def extract_facts(text: str) -> Counter:
    """Numbers, prices, dates, percentages and durations in a clause.

    Used to catch meaning flips that embeddings score as rewordings:
    "30 days" and "60 days" are nearly the same to any embedder.
    """
    facts: list[str] = []
    months = [MONTHS[m.lower()] for m in MONTH_RE.findall(text)]
    facts.extend(months)
    # Prices and percentages are taken out of the text before plain
    # numbers are counted, so their digits are not counted twice.
    prices = [p.replace(" ", "") for p in PRICE_RE.findall(text)]
    facts.extend(prices)
    text = PRICE_RE.sub(" ", text)
    percents = [p.replace(" ", "") for p in PERCENT_RE.findall(text)]
    facts.extend(percents)
    text = PERCENT_RE.sub(" ", text)
    numbers = NUMBER_RE.findall(text)
    facts.extend(numbers)
    return Counter(facts)


def counter_diff(old_counts: Counter, new_counts: Counter) -> str | None:
    """Human-readable summary of which counted items differ between two clauses."""
    only_old = old_counts - new_counts
    only_new = new_counts - old_counts
    if not only_old and not only_new:
        return None
    old_list = [f for f, n in sorted(only_old.items(), key=fact_sort_key) for _ in range(n)]
    new_list = [f for f, n in sorted(only_new.items(), key=fact_sort_key) for _ in range(n)]
    return f"old: {', '.join(old_list) or 'none'} | new: {', '.join(new_list) or 'none'}"


fact_diff = counter_diff  # the number-check summary uses the same logic


def fact_sort_key(item):
    text, _count = item
    stripped = text.lstrip("$€£")
    try:
        return (0, float(stripped.replace(",", "")), "")
    except ValueError:
        return (1, 0.0, text)


BRACKET_OPEN = "([{"
BRACKET_CLOSE = ")]}"


def join_statements(lines: list[str]) -> list[str]:
    """Join lines into one clause per balanced statement (--ignore-format).

    Lines accumulate until the bracket depth returns to zero, so a call
    that was rewrapped across several lines compares as one clause. A
    statement also ends when it closes back to one open bracket (the
    enclosing list) with a trailing comma, which keeps top-level list
    items as separate clauses instead of one file-long blob. Comment
    lines outside a statement stay their own clause. Brackets inside
    string literals are counted too, and a file that is one balanced
    expression from top to bottom (a PHP config's return array) joins
    into a single statement.
    """
    statements: list[str] = []
    buf: list[str] = []
    depth = 0
    for raw in lines:
        line = raw.strip()
        if depth == 0 and is_comment(line):
            statements.append(line)
            continue
        buf.append(line)
        net = sum(line.count(b) for b in BRACKET_OPEN)
        net -= sum(line.count(b) for b in BRACKET_CLOSE)
        depth += net
        if depth <= 0:
            statements.append(" ".join(buf))
            buf, depth = [], 0
        elif depth == 1 and net <= 0 and line.endswith(","):
            # Back at the enclosing list: the item just closed. The
            # enclosing bracket is still open, so depth stays at 1.
            statements.append(" ".join(buf))
            buf = []
    if buf:
        statements.append(" ".join(buf))
    return statements


SQL_QUERY_RE = re.compile(r"^\s*(?:select|with|values)\b", re.IGNORECASE)
SQL_WRITE_RE = re.compile(r"^\s*(?:update|delete)\b", re.IGNORECASE)
LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}
SNAPSHOT_ROW_LIMIT = 100000

JOURNAL_TABLE = "__what_changed_journal"


def _ident(name: str) -> str:
    """Quote an identifier for SQL."""
    return '"' + name.replace('"', '""') + '"'


def _sql_literal(text: str) -> str:
    """Quote a string literal for SQL."""
    return "'" + text.replace("'", "''") + "'"


def _backup_to_temp(conn) -> str:
    """Copy the database behind conn into a fresh temporary file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    dest = sqlite3.connect(path)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return path


def _install_write_triggers(conn) -> None:
    """Journal every UPDATE/DELETE row effect on the temporary copy.

    Creates one journal table and two triggers per user table. After a
    statement runs, the journal holds one row per changed row: table,
    primary key (or rowid for tables without one), and the full before
    and after values as JSON.
    """
    conn.execute(
        f"CREATE TABLE {_ident(JOURNAL_TABLE)} ("
        "seq INTEGER PRIMARY KEY AUTOINCREMENT, change TEXT, table_name TEXT,"
        " pk TEXT, before_json TEXT, after_json TEXT)"
    )
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )]
    for table in tables:
        info = conn.execute(f"PRAGMA table_info({_ident(table)})").fetchall()
        cols = [r[1] for r in info]
        pk_cols = [r[1] for r in sorted((r for r in info if r[5] > 0),
                                        key=lambda r: r[5])]
        pk_expr = (", ".join(f"OLD.{_ident(c)}" for c in pk_cols)
                   if pk_cols else "OLD.rowid")
        before = ", ".join(f"{_sql_literal(c)}, OLD.{_ident(c)}" for c in cols)
        after = ", ".join(f"{_sql_literal(c)}, NEW.{_ident(c)}" for c in cols)
        insert = (f"INSERT INTO {_ident(JOURNAL_TABLE)} "
                  "(change, table_name, pk, before_json, after_json) VALUES (")
        for tag, value_expr in (("update", f"json_array({pk_expr}), "
                                          f"json_object({before}), "
                                          f"json_object({after})"),
                                ("delete", f"json_array({pk_expr}), "
                                           f"json_object({before}), NULL")):
            conn.execute(
                f"CREATE TRIGGER {_ident(f'__wc_{tag}_{table}')} "
                f"AFTER {tag.upper()} ON {_ident(table)} FOR EACH ROW BEGIN "
                f"{insert}{_sql_literal(tag)}, {_sql_literal(table)}, {value_expr}); END"
            )


def _capture_write(conn, sql):
    """Run one write statement on the copy, journal it, roll back."""
    conn.execute("BEGIN")
    try:
        conn.execute(sql)
        rows = conn.execute(
            f"SELECT change, table_name, pk, before_json, after_json "
            f"FROM {_ident(JOURNAL_TABLE)} ORDER BY seq"
        ).fetchall()
    except (sqlite3.Error, sqlite3.Warning):
        rows = None
    finally:
        conn.execute("ROLLBACK")
    return rows


def _row_count(n: int) -> str:
    return f"{n} row{'s' if n != 1 else ''}"


def _effect_verdict(old_journal, new_journal) -> str:
    """Compare the old and new statement journals into one verdict line."""
    if sorted(map(repr, old_journal)) == sorted(map(repr, new_journal)):
        return f"same effect ({_row_count(len(old_journal))})"
    o, n = len(old_journal), len(new_journal)
    if o != n:
        return f"different effect (old {_row_count(o)}, new {_row_count(n)})"
    old_map = {(t, pk): (b, a) for _, t, pk, b, a in old_journal}
    new_map = {(t, pk): (b, a) for _, t, pk, b, a in new_journal}
    gone = sorted(set(old_map) - set(new_map))
    fresh = sorted(set(new_map) - set(old_map))
    differ = sorted(k for k in set(old_map) & set(new_map) if old_map[k] != new_map[k])
    parts = []
    for rows, name in ((gone, "only in old"), (fresh, "only in new"),
                       (differ, "changed differently")):
        if rows:
            shown = ", ".join(f"{t} {pk}" for t, pk in rows[:3])
            more = f", +{len(rows) - 3} more" if len(rows) > 3 else ""
            parts.append(f"{_row_count(len(rows))} {name}: {shown}{more}")
    return "different effect (" + "; ".join(parts) + ")"


def _is_local_host(hostname) -> bool:
    """True for localhost, the loopback addresses, or a unix socket."""
    return hostname is None or hostname == "" or hostname in LOCAL_DB_HOSTS \
        or hostname.startswith("/")


def _quote_identifier(dialect: str, name: str) -> str:
    if dialect == "mysql":
        return "`" + name.replace("`", "``") + "`"
    return '"' + name.replace('"', '""') + '"'


def _sql_literal(text: str) -> str:
    """Quote a string literal for SQL."""
    return "'" + text.replace("'", "''") + "'"


def connect_sql_check(spec: str, allow_remote: bool = False):
    """Open a connection for --sql-check.

    Accepts a SQLite file path (unchanged behaviour) or a server URL:
    postgresql://user:pass@host:port/dbname or mysql://... . Returns
    (connection, dialect). When the connection cannot be opened it prints
    the reason to stderr and returns (None, None). Non-local hosts are
    refused unless allow_remote is set.
    """
    if re.match(r"^postgres(?:ql)?://", spec):
        try:
            import psycopg
        except ImportError:
            print("hint: PostgreSQL support needs the psycopg package: "
                  'pip install "psycopg[binary]"', file=sys.stderr)
            return None, None
        parts = urlsplit(spec)
        if not _is_local_host(parts.hostname) and not allow_remote:
            print(f"refusing non-local host {parts.hostname!r} without "
                  "--allow-remote-db", file=sys.stderr)
            return None, None
        print("--sql-check warning: this must be a TEST database; every "
              "statement runs inside a rolled-back transaction", file=sys.stderr)
        return psycopg.connect(spec, autocommit=True), "postgres"
    if re.match(r"^mysql://", spec):
        try:
            import pymysql
        except ImportError:
            print("hint: MySQL support needs the PyMySQL package: "
                  "pip install PyMySQL", file=sys.stderr)
            return None, None
        parts = urlsplit(spec)
        if not _is_local_host(parts.hostname) and not allow_remote:
            print(f"refusing non-local host {parts.hostname!r} without "
                  "--allow-remote-db", file=sys.stderr)
            return None, None
        print("--sql-check warning: this must be a TEST database; every "
              "statement runs inside a rolled-back transaction", file=sys.stderr)
        conn = pymysql.connect(host=parts.hostname or "localhost",
                               port=parts.port or 3306,
                               user=parts.username or "root",
                               password=parts.password or "",
                               database=parts.path.lstrip("/") or None,
                               autocommit=True)
        return conn, "mysql"
    conn = sqlite3.connect(f"file:{spec}?mode=ro", uri=True)
    print("--sql-check warning: make sure this is a TEST database", file=sys.stderr)
    return conn, "sqlite"


def _target_table(sql):
    """The single table an UPDATE or DELETE targets, or None."""
    if re.search(r"\bjoin\b", sql, re.IGNORECASE):
        return None  # multi-table write: the simple parse declines
    m = re.match(r"\s*(?:update|delete\s+from)\s+(?:only\s+)?"
                 r"[\"'`\[]?([A-Za-z_][\w$]*)[\"'`\]]?", sql, re.IGNORECASE)
    return m.group(1) if m else None


def _is_local_host(hostname) -> bool:
    """True for localhost, the loopback addresses, or a unix socket."""
    return (hostname is None or hostname == "" or hostname in LOCAL_DB_HOSTS
            or hostname.startswith("/"))


def _quote_identifier(dialect: str, name: str) -> str:
    if dialect == "mysql":
        return "`" + name.replace("`", "``") + "`"
    return '"' + name.replace('"', '""') + '"'


def connect_sql_check(spec: str, allow_remote: bool = False):
    """Open a connection for --sql-check.

    Accepts a SQLite file path (unchanged behaviour) or a server URL:
    postgresql://user:pass@host:port/dbname or mysql://... . Returns
    (connection, dialect). When the connection cannot be opened it prints
    the reason to stderr and returns (None, None). Non-local hosts are
    refused unless allow_remote is set.
    """
    if re.match(r"^postgres(?:ql)?://", spec):
        try:
            import psycopg
        except ImportError:
            print("hint: PostgreSQL support needs the psycopg package: "
                  'pip install "psycopg[binary]"', file=sys.stderr)
            return None, None
        parts = urlsplit(spec)
        if not _is_local_host(parts.hostname) and not allow_remote:
            print(f"refusing non-local host {parts.hostname!r} without "
                  "--allow-remote-db", file=sys.stderr)
            return None, None
        print("--sql-check warning: this must be a TEST database; every "
              "statement runs inside a rolled-back transaction", file=sys.stderr)
        return psycopg.connect(spec, autocommit=True), "postgres"
    if re.match(r"^mysql://", spec):
        try:
            import pymysql
        except ImportError:
            print("hint: MySQL support needs the PyMySQL package: "
                  "pip install PyMySQL", file=sys.stderr)
            return None, None
        parts = urlsplit(spec)
        if not _is_local_host(parts.hostname) and not allow_remote:
            print(f"refusing non-local host {parts.hostname!r} without "
                  "--allow-remote-db", file=sys.stderr)
            return None, None
        print("--sql-check warning: this must be a TEST database; every "
              "statement runs inside a rolled-back transaction", file=sys.stderr)
        conn = pymysql.connect(host=parts.hostname or "localhost",
                               port=parts.port or 3306,
                               user=parts.username or "root",
                               password=parts.password or "",
                               database=parts.path.lstrip("/") or None,
                               autocommit=True)
        return conn, "mysql"
    conn = sqlite3.connect(f"file:{spec}?mode=ro", uri=True)
    print("--sql-check warning: make sure this is a TEST database", file=sys.stderr)
    return conn, "sqlite"


def _target_table(sql):
    """The single table an UPDATE or DELETE targets, or None."""
    if re.search(r"\bjoin\b", sql, re.IGNORECASE):
        return None  # multi-table write: the simple parse declines
    m = re.match(r"\s*(?:update|delete\s+from)\s+(?:only\s+)?"
                 r"[\"'`\[]?([A-Za-z_][\w$]*)[\"'`\]]?", sql, re.IGNORECASE)
    return m.group(1) if m else None


def check_sql_pair(conn, old_sql, new_sql, dialect="sqlite"):
    """Compare two matched SQL statements by running them.

    SELECT statements run in a read-only transaction and are compared by
    the rows they return. UPDATE and DELETE statements are compared by
    the rows they change. On SQLite that runs on a temporary copy of the
    database with journal triggers, each statement in its own rolled
    back transaction. On PostgreSQL and MySQL it runs directly in a
    transaction that is always rolled back, and the affected rows are
    found by snapshotting the target table before and after. The verdicts
    are the same for every engine: same rows / different rows for
    SELECTs, same effect / different effect for writes. Returns a
    one-line verdict, a "no verdict: ..." reason for a refused check, or
    None when either side is not a runnable single statement of a
    supported kind.
    """
    old_kind = ("select" if SQL_QUERY_RE.match(old_sql) else
                "write" if SQL_WRITE_RE.match(old_sql) else None)
    new_kind = ("select" if SQL_QUERY_RE.match(new_sql) else
                "write" if SQL_WRITE_RE.match(new_sql) else None)
    if old_kind is None or old_kind != new_kind:
        return None
    if dialect == "sqlite":
        return _check_sql_pair_sqlite(conn, old_sql, new_sql, old_kind)
    return _check_sql_pair_server(conn, dialect, old_sql, new_sql, old_kind)


def _check_sql_pair_sqlite(conn, old_sql, new_sql, kind):
    if kind == "select":
        try:
            old_rows = conn.execute(old_sql.strip().rstrip(";")).fetchall()
            new_rows = conn.execute(new_sql.strip().rstrip(";")).fetchall()
        except (sqlite3.Error, sqlite3.Warning):
            return None
        as_rows = lambda rows: sorted(map(repr, rows))
        if as_rows(old_rows) == as_rows(new_rows):
            return f"same rows ({len(old_rows)})"
        return f"different rows (old {len(old_rows)}, new {len(new_rows)})"
    path = _backup_to_temp(conn)
    try:
        copy_conn = sqlite3.connect(path)
        copy_conn.isolation_level = None
        try:
            _install_write_triggers(copy_conn)
            old_journal = _capture_write(copy_conn, old_sql.strip().rstrip(";"))
            new_journal = _capture_write(copy_conn, new_sql.strip().rstrip(";"))
        finally:
            copy_conn.close()
    finally:
        os.unlink(path)
    if old_journal is None or new_journal is None:
        return None
    return _effect_verdict(old_journal, new_journal)


def _check_sql_pair_server(conn, dialect, old_sql, new_sql, kind):
    if kind == "select":
        old_rows, new_rows = _server_select_rows(conn, dialect, old_sql, new_sql)
        if old_rows is None or new_rows is None:
            return None
        if sorted(map(repr, old_rows)) == sorted(map(repr, new_rows)):
            return f"same rows ({len(old_rows)})"
        return f"different rows (old {len(old_rows)}, new {len(new_rows)})"
    old_table = _target_table(old_sql)
    new_table = _target_table(new_sql)
    if old_table is None or new_table is None:
        return ("no verdict: could not find exactly one target table in "
                "the statement")
    old_journal = _server_capture_write(conn, dialect, old_sql, old_table)
    if isinstance(old_journal, str) or old_journal is None:
        return old_journal
    new_journal = _server_capture_write(conn, dialect, new_sql, new_table)
    if isinstance(new_journal, str) or new_journal is None:
        return new_journal
    return _effect_verdict(old_journal, new_journal)


def _server_select_rows(conn, dialect, sql1, sql2):
    """Run both SELECTs in one read-only transaction. Never commits."""
    cursor = conn.cursor()
    rows = None, None
    try:
        cursor.execute("BEGIN READ ONLY" if dialect == "postgres"
                       else "START TRANSACTION READ ONLY")
        if dialect == "postgres":
            cursor.execute("SET LOCAL statement_timeout = '10s'")
        else:
            cursor.execute("SET SESSION max_execution_time = 10000")
        fetched = []
        for sql in (sql1, sql2):
            cursor.execute(sql.strip().rstrip(";"))
            fetched.append(cursor.fetchall())
        rows = fetched
    except Exception:
        rows = None, None
    finally:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
    return rows


def _server_capture_write(conn, dialect, sql, table):
    """Effect of one write statement: snapshot, run, snapshot, roll back.

    Returns the journal as a list of (change, table, pk, before, after)
    tuples in the same shape the SQLite triggers produce, a
    "no verdict: ..." reason when the check is refused, or None when the
    statement errors. Never commits.
    """
    cursor = conn.cursor()
    if dialect == "mysql":
        cursor.execute("SELECT engine FROM information_schema.tables "
                       "WHERE table_schema = DATABASE() AND table_name = %s",
                       (table,))
        row = cursor.fetchone()
        engine = row[0] if row else "unknown"
        if (engine or "").lower() != "innodb":
            return (f"no verdict: table {table} uses the {engine} engine "
                    "(only InnoDB can roll back)")
    schema_filter = "current_schema()" if dialect == "postgres" else "DATABASE()"
    cursor.execute("SELECT column_name FROM information_schema.columns "
                   f"WHERE table_schema = {schema_filter} AND table_name = %s "
                   "ORDER BY ordinal_position", (table,))
    columns = [r[0] for r in cursor.fetchall()]
    if not columns:
        return f"no verdict: table {table} not found in this database"
    cursor.execute("SELECT kcu.column_name FROM information_schema.table_constraints tc "
                   "JOIN information_schema.key_column_usage kcu "
                   "ON tc.constraint_name = kcu.constraint_name "
                   "AND tc.table_schema = kcu.table_schema "
                   "AND tc.table_name = kcu.table_name "
                   f"WHERE tc.constraint_type = 'PRIMARY KEY' "
                   f"AND tc.table_schema = {schema_filter} AND tc.table_name = %s "
                   "ORDER BY kcu.ordinal_position", (table,))
    pk_cols = [r[0] for r in cursor.fetchall()]
    if not pk_cols:
        return f"no verdict: table {table} has no primary key"
    pk_idx = [columns.index(c) for c in pk_cols]
    qt = _quote_identifier(dialect, table)
    cursor.execute(f"SELECT count(*) FROM {qt}")
    count = cursor.fetchone()[0]
    if count > SNAPSHOT_ROW_LIMIT:
        return (f"no verdict: table {table} has {count} rows "
                f"(snapshot limit {SNAPSHOT_ROW_LIMIT})")
    journal = []
    try:
        cursor.execute("BEGIN" if dialect == "postgres" else "START TRANSACTION")
        if dialect == "postgres":
            cursor.execute("SET LOCAL statement_timeout = '10s'")
        else:
            cursor.execute("SET SESSION max_execution_time = 10000")
            cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")

        def snapshot():
            cursor.execute(f"SELECT * FROM {qt}")
            return {tuple(row[i] for i in pk_idx): row for row in cursor.fetchall()}

        before = snapshot()
        cursor.execute(sql)
        after = snapshot()
    except Exception:
        return None
    finally:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
    for pk in sorted(before.keys() - after.keys(), key=repr):
        journal.append(("delete", table, json.dumps(pk, default=str),
                        json.dumps(before[pk], default=str), None))
    for pk in sorted(before.keys() & after.keys(), key=repr):
        if before[pk] != after[pk]:
            journal.append(("update", table, json.dumps(pk, default=str),
                            json.dumps(before[pk], default=str),
                            json.dumps(after[pk], default=str)))
    for pk in sorted(after.keys() - before.keys(), key=repr):
        journal.append(("insert", table, json.dumps(pk, default=str),
                        None, json.dumps(after[pk], default=str)))
    return journal


class Pair:
    __slots__ = ("label", "old", "new", "sim", "reason", "sql")

    def __init__(self, label, old, new, sim, reason):
        self.label = label  # unchanged | reworded | changed | added | removed
        self.old = old
        self.new = new
        self.sim = sim
        self.reason = reason
        self.sql = None     # same rows / different rows, from --sql-check


def compare(old_text: str, new_text: str, model, threshold: float, floor: float,
            max_tokens: int = DEFAULT_MAX_TOKENS,
            claim_check: bool = True, claim_words=None, code_mode: bool = False,
            ignore_format: bool = False):
    """Match clauses across versions and label every pair."""
    if code_mode:
        lines_old, lines_new = split_lines(old_text), split_lines(new_text)
        if ignore_format:
            old_clauses = join_statements(lines_old)
            new_clauses = join_statements(lines_new)
        else:
            old_clauses, new_clauses = lines_old, lines_new
    else:
        old_clauses = split_clauses(old_text)
        new_clauses = split_clauses(new_text)

    def exact_key(clause: str) -> str:
        # Code compares case sensitively: TRUE and true are not the same line.
        # With --ignore-format, quote style is normalised too, so 'x' and "x"
        # are the same line.
        text = format_normalize(clause) if ignore_format else normalize(clause)
        return text if code_mode else text.lower()

    # Warn about clauses the model would have to truncate.
    for clause in old_clauses + new_clauses:
        n_tokens = len(model.tokenizer(clause, add_special_tokens=False)["input_ids"])
        if n_tokens > max_tokens:
            print(f"warning: clause over {max_tokens} tokens will be truncated: {clause[:80]}...",
                  file=sys.stderr)

    pairs: list[Pair] = []

    # 1. Exact matches are Unchanged, no embedding needed.
    old_by_text: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(old_clauses):
        old_by_text[exact_key(c)].append(i)
    old_exact, new_exact = set(), set()
    for j, c in enumerate(new_clauses):
        key = exact_key(c)
        if old_by_text[key]:
            i = old_by_text[key].pop()
            old_exact.add(i)
            new_exact.add(j)
            pairs.append(Pair("unchanged", old_clauses[i], c, 1.0, "identical text"))

    # 2. Everything else: embed as plain text (no prompts) and match greedily.
    old_rest = [i for i in range(len(old_clauses)) if i not in old_exact]
    new_rest = [j for j in range(len(new_clauses)) if j not in new_exact]
    if old_rest and new_rest:
        old_vecs = model.encode(old_clauses, normalize_embeddings=True)
        new_vecs = model.encode(new_clauses, normalize_embeddings=True)
        old_facts = [extract_facts(old_clauses[i]) for i in old_rest]
        old_claims = [extract_claims(old_clauses[i], claim_words) for i in old_rest] if claim_check else None
        sim = old_vecs[old_rest] @ new_vecs[new_rest].T  # vectors are unit length

        taken_old, taken_new = set(), set()
        order = np.argsort(sim.ravel())[::-1]
        for flat in order:
            a, b = divmod(int(flat), sim.shape[1])
            if sim[a, b] < floor:
                break
            if a in taken_old or b in taken_new:
                continue
            i, j = old_rest[a], new_rest[b]
            score = float(sim[a, b])
            # Below the reword threshold, a pair must be the overall nearest
            # match of both sides across the whole other document. Otherwise
            # two unrelated leftovers grab each other and a genuinely
            # removed clause shows up as a fake Changed pair.
            if score < threshold:
                best_old_for_j = int(np.argmax(old_vecs @ new_vecs[j]))
                best_new_for_i = int(np.argmax(new_vecs @ old_vecs[i]))
                if best_old_for_j != i or best_new_for_i != j:
                    continue
            taken_old.add(a)
            taken_new.add(b)
            diff = counter_diff(old_facts[a], extract_facts(new_clauses[j]))
            claim_diff = None
            if claim_check:
                claim_diff = counter_diff(old_claims[a], extract_claims(new_clauses[j], claim_words))
            if diff:
                pairs.append(Pair("changed", old_clauses[i], new_clauses[j], score,
                                  f"numbers/dates differ ({diff})"))
            elif claim_diff:
                pairs.append(Pair("changed", old_clauses[i], new_clauses[j], score,
                                  f"claim words differ ({claim_diff})"))
            elif code_mode and not (is_comment(old_clauses[i]) and is_comment(new_clauses[j])):
                # In code there is no harmless rewording outside comments: any
                # text change on a live line is a real change, whatever the
                # score says. Comments keep the prose Reworded/Changed logic.
                if ignore_format:
                    old_side, new_side = format_normalize(old_clauses[i]), format_normalize(new_clauses[j])
                else:
                    old_side, new_side = old_clauses[i], new_clauses[j]
                token_change = token_diff(old_side, new_side) or "text differs"
                pairs.append(Pair("changed", old_clauses[i], new_clauses[j], score,
                                  f"text differs ({token_change})"))
            elif score >= threshold:
                pairs.append(Pair("reworded", old_clauses[i], new_clauses[j], score,
                                  "same meaning, different words"))
            else:
                pairs.append(Pair("changed", old_clauses[i], new_clauses[j], score,
                                  f"related but sim {score:.2f} < {threshold:.2f}"))
        # 3. Whatever never found a close partner is Added or Removed.
        for a in range(len(old_rest)):
            if a not in taken_old:
                pairs.append(Pair("removed", old_clauses[old_rest[a]], None, None, "no close match in new"))
        for b in range(len(new_rest)):
            if b not in taken_new:
                pairs.append(Pair("added", None, new_clauses[new_rest[b]], None, "no close match in old"))
    else:
        for i in old_rest:
            pairs.append(Pair("removed", old_clauses[i], None, None, "no close match in new"))
        for j in new_rest:
            pairs.append(Pair("added", None, new_clauses[j], None, "no close match in old"))

    return pairs


LABEL_ORDER = ["changed", "added", "removed", "reworded", "unchanged"]
LABEL_COUNTS_ORDER = ["unchanged", "reworded", "changed", "added", "removed"]


def eval_hard_cases(csv_path, model, threshold, floor, claim_check=True, claim_words=None,
                    max_tokens=DEFAULT_MAX_TOKENS, show_pairs=True):
    """Label each old/new pair in a CSV and score against the expected label.

    The CSV needs columns old, new, expected. An empty new cell means the old
    clause was removed. Expected labels: changed or removed.
    """
    import csv
    rows = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append((row["old"].strip(), row["new"].strip(), row["expected"].strip()))
    results = []
    for old, new, expected in rows:
        pairs = compare(old, new, model, threshold, floor, max_tokens,
                        claim_check=claim_check, claim_words=claim_words)
        predicted = pairs[0].label if pairs else "unchanged"
        reason = pairs[0].reason if pairs else ""
        sim = pairs[0].sim if pairs else None
        results.append((old, new, expected, predicted, sim, reason))
    hits = sum(1 for r in results if r[2] == r[3])
    print(f"HARD CASES: {csv_path}")
    if show_pairs:
        for k, (old, new, expected, predicted, sim, reason) in enumerate(results, 1):
            mark = "ok  " if expected == predicted else "MISS"
            sim_text = f"sim {sim:.2f}, " if sim is not None else ""
            new_text = new if new else "(empty, clause removed)"
            print(f"{k}. [{mark}] expected {expected}, predicted {predicted} ({sim_text}{reason})")
            print(f"   old: {old}")
            print(f"   new: {new_text}")
    print(f"accuracy: {hits}/{len(results)} = {hits / len(results):.0%}")
    print("")
    return hits, len(results)


def render_report(pairs: list[Pair], old_path, new_path, model_id, threshold, floor, show_all):
    lines = []
    counts = Counter(p.label for p in pairs)
    lines.append("WHAT REALLY CHANGED")
    lines.append(f"old: {old_path}")
    lines.append(f"new: {new_path}")
    lines.append(f"model: {model_id} | reword threshold {threshold:.2f} | related floor {floor:.2f}")
    lines.append("")
    lines.append("COUNTS")
    for label in LABEL_COUNTS_ORDER:
        note = ""
        if label == "reworded" and counts[label] and not show_all:
            note = "  (hidden, run with --show-all to see them)"
        lines.append(f"{label:<10} {counts[label]:>3}{note}")
    lines.append("")

    def clause_text(pair, side):
        text = pair.old if side == "old" else pair.new
        return text if text is not None else "(none)"

    for label in LABEL_ORDER:
        items = [p for p in pairs if p.label == label]
        if label in ("reworded", "unchanged") and not show_all:
            continue
        lines.append(f"{label.upper()}")
        if not items:
            lines.append("(none)")
            lines.append("")
            continue
        for k, p in enumerate(items, 1):
            if label == "changed":
                lines.append(f"{k}. [{p.reason}, sim {p.sim:.2f}]")
                lines.append(f"   old: {clause_text(p, 'old')}")
                lines.append(f"   new: {clause_text(p, 'new')}")
                if p.sql:
                    lines.append(f"   sql: {p.sql}")
            elif label == "reworded":
                lines.append(f"{k}. [sim {p.sim:.2f}]")
                lines.append(f"   old: {clause_text(p, 'old')}")
                lines.append(f"   new: {clause_text(p, 'new')}")
                if p.sql:
                    lines.append(f"   sql: {p.sql}")
            elif label == "unchanged":
                lines.append(f"{k}. {clause_text(p, 'old')}")
            else:  # added / removed
                text = clause_text(p, "new" if label == "added" else "old")
                lines.append(f"+ {text}" if label == "added" else f"- {text}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("old", nargs="?", help="path to the old version")
    ap.add_argument("new", nargs="?", help="path to the new version")
    ap.add_argument("--hard-cases", metavar="CSV",
                    help="evaluate a CSV of pairs (columns: old,new,expected) instead of a document pair")
    ap.add_argument("--model", default=MODEL_ID)
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help="similarity above which a pair is Reworded (default %(default)s)")
    ap.add_argument("--floor", type=float, default=DEFAULT_FLOOR,
                    help="similarity below which a clause is Added/Removed (default %(default)s)")
    ap.add_argument("--claim-words", metavar="A,B,C", default=None,
                    help="comma-separated risky phrases to check (default: built-in list)")
    ap.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS,
                    help="token budget per clause; the model reads 512 tokens "
                         "by default, up to 2,048 if you raise the limit "
                         "(default %(default)s)")
    ap.add_argument("--no-claim-check", action="store_true",
                    help="disable the claim-words check")
    ap.add_argument("--show-all", action="store_true", help="also print Unchanged and Reworded clauses")
    ap.add_argument("--code", action="store_true",
                    help="code or config files: split by line only, and any text "
                         "change on a non-comment line counts as Changed")
    ap.add_argument("--ignore-format", action="store_true",
                    help="with --code: normalise quote style and whitespace, and "
                         "join lines into balanced statements, so pure reformatting "
                         "is not reported")
    ap.add_argument("--sql-check", metavar="DB_FILE_OR_URL",
                    help="run matched SQL pairs against a copy of a SQLite "
                         "database file, or against a PostgreSQL or MySQL test "
                         "database given as a URL (postgresql://... or mysql://...)")
    ap.add_argument("--allow-remote-db", action="store_true",
                    help="let --sql-check run against a non-local PostgreSQL or "
                         "MySQL host (default: localhost only)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    if not args.hard_cases and (not args.old or not args.new):
        ap.error("provide old and new file paths, or --hard-cases CSV")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(args.model, revision=MODEL_REVISION,
                                trust_remote_code=True)
    max_tokens = min(args.max_tokens, MAX_TOKEN_LIMIT)

    claim_words = [w.strip() for w in args.claim_words.split(",")] if args.claim_words else None
    claim_check = not args.no_claim_check

    if args.hard_cases:
        eval_hard_cases(args.hard_cases, model, args.threshold, args.floor,
                        claim_check, claim_words, max_tokens)
        return

    with open(args.old, encoding="utf-8") as f:
        old_text = f.read()
    with open(args.new, encoding="utf-8") as f:
        new_text = f.read()

    pairs = compare(old_text, new_text, model, args.threshold, args.floor,
                    max_tokens, claim_check, claim_words, code_mode=args.code,
                    ignore_format=args.ignore_format)
    conn = None
    dialect = "sqlite"
    if args.sql_check:
        conn, dialect = connect_sql_check(args.sql_check,
                                          allow_remote=args.allow_remote_db)
    if conn is not None:
        for p in pairs:
            if p.label in ("changed", "reworded") and p.old and p.new:
                p.sql = check_sql_pair(conn, p.old, p.new, dialect)
    if args.json:
        print(json.dumps([{
            "label": p.label, "old": p.old, "new": p.new,
            "sim": p.sim, "reason": p.reason, "sql": p.sql,
        } for p in pairs], indent=2))
    else:
        print(render_report(pairs, args.old, args.new, args.model,
                            args.threshold, args.floor, args.show_all))
    if conn:
        conn.close()


if __name__ == "__main__":
    main()
