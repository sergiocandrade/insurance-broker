-- Demo broker and user data. All identifiers are deterministic and emails use example.com.
-- User-to-broker memberships are inserted after both parent records exist.

INSERT INTO brokers (id, status, activated_at)
SELECT seed.id, seed.status, seed.activated_at
FROM (
    SELECT 'b1000000-0000-4000-8000-000000000001' AS id, 'ACTIVE' AS status, CURRENT_TIMESTAMP AS activated_at
    UNION ALL SELECT 'b1000000-0000-4000-8000-000000000002', 'ACTIVE', CURRENT_TIMESTAMP
    UNION ALL SELECT 'b1000000-0000-4000-8000-000000000003', 'PENDING', NULL
    UNION ALL SELECT 'b1000000-0000-4000-8000-000000000004', 'ACTIVE', CURRENT_TIMESTAMP
    UNION ALL SELECT 'b1000000-0000-4000-8000-000000000005', 'PENDING', NULL
) AS seed
WHERE NOT EXISTS (
    SELECT 1 FROM brokers existing WHERE existing.id = seed.id
);

INSERT INTO users (id, email, name, external_id, activated_at, status)
SELECT seed.id, seed.email, seed.name, seed.external_id, seed.activated_at, seed.status
FROM (
    SELECT 'a1000000-0000-4000-8000-000000000001' AS id,
           'marina.almeida@example.com' AS email, 'Marina Almeida' AS name,
           NULL AS external_id, NULL AS activated_at, 'PENDING' AS status
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000002', 'caio.rocha@example.com', 'Caio Rocha', NULL, NULL, 'PENDING'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000003', 'luiza.martins@example.com', 'Luiza Martins', NULL, NULL, 'PENDING'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000004', 'rafael.nunes@example.com', 'Rafael Nunes', NULL, NULL, 'PENDING'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000005', 'beatriz.lopes@example.com', 'Beatriz Lopes', NULL, NULL, 'PENDING'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000006', 'contato.arvore@example.com', 'Arvore Comercio Ltda.', NULL, NULL, 'PENDING'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000007', 'contato.pioneira@example.com', 'Pioneira Servicos Ltda.', NULL, NULL, 'PENDING'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000008', 'contato.norte@example.com', 'Norte Logistica Ltda.', NULL, NULL, 'PENDING'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000009', 'helena.freitas@example.com', 'Helena Freitas', 'demo-cognito-user-009', CURRENT_TIMESTAMP, 'REGISTERED'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000010', 'miguel.cardoso@example.com', 'Miguel Cardoso', 'demo-cognito-user-010', CURRENT_TIMESTAMP, 'REGISTERED'
) AS seed
WHERE NOT EXISTS (
    SELECT 1
    FROM users existing
    WHERE existing.id = seed.id OR existing.email = seed.email
);

INSERT INTO users_brokers (user_id, broker_id)
SELECT seed.user_id, seed.broker_id
FROM (
    SELECT 'a1000000-0000-4000-8000-000000000001' AS user_id, 'b1000000-0000-4000-8000-000000000001' AS broker_id
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000002', 'b1000000-0000-4000-8000-000000000001'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000003', 'b1000000-0000-4000-8000-000000000002'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000004', 'b1000000-0000-4000-8000-000000000002'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000005', 'b1000000-0000-4000-8000-000000000003'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000006', 'b1000000-0000-4000-8000-000000000003'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000007', 'b1000000-0000-4000-8000-000000000004'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000008', 'b1000000-0000-4000-8000-000000000004'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000009', 'b1000000-0000-4000-8000-000000000005'
    UNION ALL SELECT 'a1000000-0000-4000-8000-000000000010', 'b1000000-0000-4000-8000-000000000005'
) AS seed
JOIN users u ON u.id = seed.user_id
JOIN brokers b ON b.id = seed.broker_id
WHERE NOT EXISTS (
    SELECT 1
    FROM users_brokers existing
    WHERE existing.user_id = seed.user_id AND existing.broker_id = seed.broker_id
);
