-- Creates the customers table
CREATE TABLE customers (
    id BIGINT PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    name VARCHAR(255),
    phone VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending',
    credit_limit DECIMAL(10,2) DEFAULT 500.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    customer_id BIGINT REFERENCES customers(id) ON DELETE SET NULL,
    total DECIMAL(10,2) NOT NULL
);
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_orders_customer ON orders(customer_id);
