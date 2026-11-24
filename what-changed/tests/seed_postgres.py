"""Load the what-changed SQL fixture data into a PostgreSQL test database.

Reads the server URL from HOBBYLM_PG_URL (for example
postgresql://user:pass@localhost:5432/what_changed_test). The database
must exist. Re-creates the users and orders tables, so do not point it
at a database you care about.
"""
import os
import sys

SEED_USERS = [
    (1, "Ada Lovelace", "ada@example.com", "active", 36),
    (2, "Grace Hopper", "grace@example.com", "active", 45),
    (3, "Edsger Dijkstra", None, "pending", 20),
    (4, "Donald Knuth", "knuth@example.com", "inactive", 17),
    (5, "Barbara Liskov", "liskov@example.com", "pending", 19),
]
SEED_ORDERS = [
    (1, 1, 25.50), (2, 1, 89.99), (3, 2, 10.00),
    (4, 2, 250.00), (5, 1, 100.00), (6, 2, 99.95),
]


def main():
    url = os.environ.get("HOBBYLM_PG_URL")
    if not url:
        print("set HOBBYLM_PG_URL (postgresql://user:pass@localhost:5432/db) "
              "to seed PostgreSQL")
        return 1
    try:
        import psycopg
    except ImportError:
        print('hint: pip install "psycopg[binary]"')
        return 1
    with psycopg.connect(url, autocommit=True) as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS orders")
        cur.execute("DROP TABLE IF EXISTS users")
        cur.execute("""CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            status TEXT NOT NULL,
            age INTEGER NOT NULL)""")
        cur.execute("""CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            total REAL NOT NULL)""")
        cur.executemany("INSERT INTO users (id, name, email, status, age) "
                        "VALUES (%s, %s, %s, %s, %s)", SEED_USERS)
        cur.executemany("INSERT INTO orders (id, user_id, total) "
                        "VALUES (%s, %s, %s)", SEED_ORDERS)
        cur.execute("SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM orders)")
        users, orders = cur.fetchone()
        print(f"seeded PostgreSQL: {users} users, {orders} orders")
    return 0


if __name__ == "__main__":
    sys.exit(main())
