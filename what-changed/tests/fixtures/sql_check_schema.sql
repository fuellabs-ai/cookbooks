-- Schema and rows for the --sql-check tests. Written for this recipe;
-- the people in it are computing pioneers, not real customers.
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    status TEXT NOT NULL,
    age INTEGER NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total REAL NOT NULL
);
INSERT INTO users (name, email, status, age) VALUES
    ('Ada Lovelace', 'ada@example.com', 'active', 36),
    ('Grace Hopper', 'grace@example.com', 'active', 45),
    ('Edsger Dijkstra', NULL, 'pending', 20),
    ('Donald Knuth', 'knuth@example.com', 'inactive', 17),
    ('Barbara Liskov', 'liskov@example.com', 'pending', 19);
INSERT INTO orders (user_id, total) VALUES
    (1, 25.50),
    (1, 89.99),
    (2, 10.00),
    (2, 250.00),
    (3, 100.00),
    (5, 99.95);
