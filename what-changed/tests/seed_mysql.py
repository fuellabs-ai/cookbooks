"""Load the what-changed SQL fixture data into a MySQL test database.

Reads the server URL from HOBBYLM_MYSQL_URL (for example
mysql://root@127.0.0.1:3306/what_changed_test). The database must exist.
Re-creates the users and orders tables, so do not point it at a database
you care about.
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
    url = os.environ.get("HOBBYLM_MYSQL_URL")
    if not url:
        print("set HOBBYLM_MYSQL_URL (mysql://user:pass@127.0.0.1:3306/db) "
              "to seed MySQL")
        return 1
    try:
        import pymysql
    except ImportError:
        print("hint: pip install PyMySQL")
        return 1
    parts = urlsplit(url)
    conn = pymysql.connect(host=parts.hostname or "localhost",
                           port=parts.port or 3306,
                           user=parts.username or "root",
                           password=parts.password or "",
                           database=parts.path.lstrip("/") or None,
                           autocommit=True)
    with conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS orders")
        cur.execute("DROP TABLE IF EXISTS users")
        cur.execute("""CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(200),
            status VARCHAR(20) NOT NULL,
            age INTEGER NOT NULL
        ) ENGINE=InnoDB""")
        cur.execute("""CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            total DOUBLE NOT NULL
        ) ENGINE=InnoDB""")
        cur.executemany("INSERT INTO users (id, name, email, status, age) "
                        "VALUES (%s, %s, %s, %s, %s)", SEED_USERS)
        cur.executemany("INSERT INTO orders (id, user_id, total) "
                        "VALUES (%s, %s, %s)", SEED_ORDERS)
        cur.execute("SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM orders)")
        users, orders = cur.fetchone()
        print(f"seeded MySQL: {users} users, {orders} orders")
    return 0


if __name__ == "__main__":
    from urllib.parse import urlsplit
    sys.exit(main())
