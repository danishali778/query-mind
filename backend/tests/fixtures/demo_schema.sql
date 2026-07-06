-- Demo schema for agent evaluation (PostgreSQL)
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    sku TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id UUID REFERENCES orders(id),
    product_id UUID REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY,
    order_id UUID REFERENCES orders(id),
    amount NUMERIC(12, 2) NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    event TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

INSERT INTO customers (id, name, email, created_at) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Acme Corp', 'acme@example.com', NOW() - INTERVAL '120 days'),
    ('22222222-2222-2222-2222-222222222222', 'Beta LLC', 'beta@example.com', NOW() - INTERVAL '10 days')
ON CONFLICT DO NOTHING;

INSERT INTO products (id, name, category, sku) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Widget', 'enterprise', 'W-001')
ON CONFLICT DO NOTHING;

INSERT INTO orders (id, customer_id, created_at, status) VALUES
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '11111111-1111-1111-1111-111111111111', NOW() - INTERVAL '60 days', 'paid'),
    ('cccccccc-cccc-cccc-cccc-cccccccccccc', '22222222-2222-2222-2222-222222222222', NOW() - INTERVAL '5 days', 'paid')
ON CONFLICT DO NOTHING;

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 2, 50.00),
    ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 1, 75.00)
ON CONFLICT DO NOTHING;

INSERT INTO payments (id, order_id, amount, status) VALUES
    ('dddddddd-dddd-dddd-dddd-dddddddddddd', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 100.00, 'paid'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 75.00, 'paid')
ON CONFLICT DO NOTHING;
