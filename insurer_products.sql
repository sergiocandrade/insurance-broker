
INSERT INTO insurer_products (
    insurer_id,
    product_id
)
SELECT
    i.id,
    ip.id
FROM (
    SELECT 'Porto Seguro' AS insurer_name,
           'AUTO-001' AS product_code
    UNION ALL SELECT 'Porto Seguro', 'AUTO-002'
    UNION ALL SELECT 'Porto Seguro', 'RES-001'
    UNION ALL SELECT 'Porto Seguro', 'RES-002'
    UNION ALL SELECT 'Porto Seguro', 'CEL-001'
    UNION ALL SELECT 'Porto Seguro', 'VIDA-001'

    UNION ALL SELECT 'Bradesco Seguros', 'AUTO-001'
    UNION ALL SELECT 'Bradesco Seguros', 'RES-001'
    UNION ALL SELECT 'Bradesco Seguros', 'VIDA-001'
    UNION ALL SELECT 'Bradesco Seguros', 'VIDA-002'
    UNION ALL SELECT 'Bradesco Seguros', 'PREST-001'
    UNION ALL SELECT 'Bradesco Seguros', 'VIAG-001'

    UNION ALL SELECT 'Tokio Marine Seguradora', 'AUTO-001'
    UNION ALL SELECT 'Tokio Marine Seguradora', 'AUTO-002'
    UNION ALL SELECT 'Tokio Marine Seguradora', 'EMP-001'
    UNION ALL SELECT 'Tokio Marine Seguradora', 'RC-001'
    UNION ALL SELECT 'Tokio Marine Seguradora', 'TRAN-001'

    UNION ALL SELECT 'Allianz Seguros', 'AUTO-001'
    UNION ALL SELECT 'Allianz Seguros', 'FROT-001'
    UNION ALL SELECT 'Allianz Seguros', 'EMP-001'
    UNION ALL SELECT 'Allianz Seguros', 'ENG-001'
    UNION ALL SELECT 'Allianz Seguros', 'TRAN-002'
    UNION ALL SELECT 'Allianz Seguros', 'CYBER-001'

    UNION ALL SELECT 'MAPFRE Seguros', 'AUTO-001'
    UNION ALL SELECT 'MAPFRE Seguros', 'RES-001'
    UNION ALL SELECT 'MAPFRE Seguros', 'AGRO-001'
    UNION ALL SELECT 'MAPFRE Seguros', 'PEC-001'
    UNION ALL SELECT 'MAPFRE Seguros', 'VIAG-001'

    UNION ALL SELECT 'Zurich Seguros', 'RES-001'
    UNION ALL SELECT 'Zurich Seguros', 'EMP-001'
    UNION ALL SELECT 'Zurich Seguros', 'VIDA-002'
    UNION ALL SELECT 'Zurich Seguros', 'RC-002'
    UNION ALL SELECT 'Zurich Seguros', 'CYBER-001'

    UNION ALL SELECT 'Chubb Seguros', 'CEL-001'
    UNION ALL SELECT 'Chubb Seguros', 'NOTE-001'
    UNION ALL SELECT 'Chubb Seguros', 'AP-001'
    UNION ALL SELECT 'Chubb Seguros', 'RC-002'
    UNION ALL SELECT 'Chubb Seguros', 'DO-001'

    UNION ALL SELECT 'Pottencial Seguradora', 'SG-001'
    UNION ALL SELECT 'Pottencial Seguradora', 'EMP-001'
    UNION ALL SELECT 'Pottencial Seguradora', 'ENG-001'

    UNION ALL SELECT 'Junto Seguros', 'SG-001'
    UNION ALL SELECT 'Junto Seguros', 'EMP-001'
    UNION ALL SELECT 'Junto Seguros', 'ENG-001'

    UNION ALL SELECT 'Too Seguros', 'CEL-001'
    UNION ALL SELECT 'Too Seguros', 'NOTE-001'
    UNION ALL SELECT 'Too Seguros', 'GAR-001'
) AS seed
JOIN insurers i
    ON LOWER(i.name) = LOWER(seed.insurer_name)
JOIN insurance_products ip
    ON ip.product_code = seed.product_code
WHERE NOT EXISTS (
    SELECT 1
    FROM insurer_products existing
    WHERE existing.insurer_id = i.id
      AND existing.product_id = ip.id
);
