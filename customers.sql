-- Demo customers use reserved example.com email addresses and fictional phone numbers.
-- Customers are assigned round-robin across all existing brokers. No rows are inserted if none exists.
INSERT INTO customers (
    id,
    name,
    customer_type,
    phone,
    email,
    broker_id
)
SELECT
    seed.id,
    seed.name,
    seed.customer_type,
    seed.phone,
    seed.email,
    broker.id
FROM (
    SELECT 1 AS customer_number,
           'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5001' AS id,
           'Ana Oliveira' AS name,
           'PERSON' AS customer_type,
           '+55 11 90000-0001' AS phone,
           'ana.oliveira@example.com' AS email
    UNION ALL SELECT 2, 'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5002', 'Bruno Santos', 'PERSON', '+55 21 90000-0002', 'bruno.santos@example.com'
    UNION ALL SELECT 3, 'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5003', 'Carla Mendes', 'PERSON', '+55 31 90000-0003', 'carla.mendes@example.com'
    UNION ALL SELECT 4, 'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5004', 'Diego Costa', 'PERSON', '+55 41 90000-0004', 'diego.costa@example.com'
    UNION ALL SELECT 5, 'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5005', 'Eduarda Lima', 'PERSON', '+55 51 90000-0005', 'eduarda.lima@example.com'
    UNION ALL SELECT 6, 'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5006', 'Alfa Comércio Ltda.', 'BUSINESS', '+55 11 3000-0006', 'contato.alfa@example.com'
    UNION ALL SELECT 7, 'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5007', 'Horizonte Tecnologia Ltda.', 'BUSINESS', '+55 21 3000-0007', 'contato.horizonte@example.com'
    UNION ALL SELECT 8, 'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5008', 'Vale Verde Alimentos Ltda.', 'BUSINESS', '+55 31 3000-0008', 'contato.valeverde@example.com'
    UNION ALL SELECT 9, 'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5009', 'Nuvem Azul Serviços Ltda.', 'BUSINESS', '+55 41 3000-0009', 'contato.nuvemazul@example.com'
    UNION ALL SELECT 10, 'f1f0a3b2-7d4c-4a81-9a20-1c2d3e4f5010', 'Ponte Nova Logística Ltda.', 'BUSINESS', '+55 51 3000-0010', 'contato.pontenova@example.com'
) AS seed
JOIN (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY id) AS broker_number,
           COUNT(*) OVER () AS broker_count
    FROM brokers
) AS broker ON 1 = 1
WHERE broker.broker_number = ((seed.customer_number - 1) % broker.broker_count) + 1
  AND NOT EXISTS (
    SELECT 1
    FROM customers existing
    WHERE existing.id = seed.id OR existing.email = seed.email
);
