-- Demo policies; run after customers.sql and products.sql.
-- Uses reserved example.com emails and only inserts policies whose customer/product exists.
INSERT INTO policies (
    id,
    customer_id,
    amount,
    status,
    policy_number,
    start_date,
    end_date,
    insurance_product_id
)
SELECT
    seed.id,
    customer.id,
    seed.amount,
    seed.status,
    seed.policy_number,
    seed.start_date,
    seed.end_date,
    product.id
FROM (
    SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6001' AS id,
           'POL-DEMO-0001' AS policy_number,
           'ana.oliveira@example.com' AS customer_email,
           'Automóvel' AS branch_name,
           'AUTO-001' AS product_code,
           1250.00 AS amount,
           'ACTIVE' AS status,
           '2026-01-01' AS start_date,
           '2026-12-31' AS end_date
    UNION ALL SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6002', 'POL-DEMO-0002', 'bruno.santos@example.com', 'Motocicleta', 'MOTO-001', 890.00, 'ACTIVE', '2026-02-01', '2027-01-31'
    UNION ALL SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6003', 'POL-DEMO-0003', 'carla.mendes@example.com', 'Residencial', 'RES-001', 540.00, 'ACTIVE', '2026-03-01', '2027-02-28'
    UNION ALL SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6004', 'POL-DEMO-0004', 'diego.costa@example.com', 'Residencial', 'RES-002', 760.00, 'PENDING', '2026-10-01', '2027-09-30'
    UNION ALL SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6005', 'POL-DEMO-0005', 'eduarda.lima@example.com', 'Celular', 'CEL-001', 310.00, 'ACTIVE', '2026-04-15', '2027-04-14'
    UNION ALL SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6006', 'POL-DEMO-0006', 'contato.alfa@example.com', 'Vida em Grupo', 'VIDA-002', 4800.00, 'ACTIVE', '2026-05-01', '2027-04-30'
    UNION ALL SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6007', 'POL-DEMO-0007', 'contato.horizonte@example.com', 'Empresarial', 'EMP-001', 9250.00, 'PENDING', '2026-10-15', '2027-10-14'
    UNION ALL SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6008', 'POL-DEMO-0008', 'contato.valeverde@example.com', 'Agrícola', 'AGRO-001', 15300.00, 'ACTIVE', '2026-06-01', '2027-05-31'
    UNION ALL SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6009', 'POL-DEMO-0009', 'contato.nuvemazul@example.com', 'Riscos Cibernéticos', 'CYBER-001', 6800.00, 'ACTIVE', '2026-07-01', '2027-06-30'
    UNION ALL SELECT 'f2a0b3c4-8d5e-4b91-9a20-2c3d4e5f6010', 'POL-DEMO-0010', 'contato.pontenova@example.com', 'Transporte Nacional', 'TRAN-001', 4100.00, 'ACTIVE', '2026-08-01', '2027-07-31'
) AS seed
JOIN customers customer
    ON LOWER(customer.email) = LOWER(seed.customer_email)
JOIN insurance_products product
    ON product.product_code = seed.product_code
JOIN insurance_branches branch
    ON branch.id = product.branch_id
   AND LOWER(branch.name) = LOWER(seed.branch_name)
WHERE NOT EXISTS (
    SELECT 1
    FROM policies existing
    WHERE existing.policy_number = seed.policy_number
);
