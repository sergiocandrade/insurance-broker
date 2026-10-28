
INSERT INTO insurance_products (
    id,
    branch_id,
    name,
    product_code
)
SELECT
    UUID(),
    ib.id,
    v.product_name,
    v.product_code
FROM (
    SELECT 'Automóvel' AS branch_name,
           'Auto Essencial' AS product_name,
           'AUTO-001' AS product_code
    UNION ALL SELECT 'Automóvel', 'Auto Completo Plus', 'AUTO-002'
    UNION ALL SELECT 'Motocicleta', 'Moto Protegida', 'MOTO-001'
    UNION ALL SELECT 'Frota de Veículos', 'Frota Empresarial', 'FROT-001'

    UNION ALL SELECT 'Residencial', 'Residencial Essencial', 'RES-001'
    UNION ALL SELECT 'Residencial', 'Residencial Premium', 'RES-002'
    UNION ALL SELECT 'Condomínio', 'Condomínio Seguro', 'COND-001'
    UNION ALL SELECT 'Empresarial', 'Empresa Protegida', 'EMP-001'
    UNION ALL SELECT 'Equipamentos', 'Equipamentos Seguros', 'EQUIP-001'

    UNION ALL SELECT 'Vida Individual', 'Vida Fácil', 'VIDA-001'
    UNION ALL SELECT 'Vida em Grupo', 'Vida Corporativa', 'VIDA-002'
    UNION ALL SELECT 'Acidentes Pessoais', 'Acidentes Protegidos', 'AP-001'
    UNION ALL SELECT 'Funeral', 'Assistência Familiar', 'FUN-001'

    UNION ALL SELECT 'Prestamista', 'Proteção Financeira', 'PREST-001'
    UNION ALL SELECT 'Garantia Estendida', 'Garantia Extra', 'GAR-001'
    UNION ALL SELECT 'Seguro Garantia', 'Garantia Contratual', 'SG-001'

    UNION ALL SELECT 'Seguro Viagem', 'Viagem Tranquila', 'VIAG-001'
    UNION ALL SELECT 'Celular', 'Celular Protegido', 'CEL-001'
    UNION ALL SELECT 'Equipamentos Portáteis', 'Notebook Seguro', 'NOTE-001'

    UNION ALL SELECT 'Responsabilidade Civil Geral', 'RC Empresa', 'RC-001'
    UNION ALL SELECT 'Responsabilidade Civil Profissional', 'RC Profissional Plus', 'RC-002'
    UNION ALL SELECT 'D&O', 'Executivos Protegidos', 'DO-001'
    UNION ALL SELECT 'Riscos Cibernéticos', 'Cyber Proteção', 'CYBER-001'

    UNION ALL SELECT 'Transporte Nacional', 'Carga Segura Brasil', 'TRAN-001'
    UNION ALL SELECT 'Transporte Internacional', 'Carga Global', 'TRAN-002'

    UNION ALL SELECT 'Agrícola', 'Safra Protegida', 'AGRO-001'
    UNION ALL SELECT 'Pecuário', 'Rebanho Seguro', 'PEC-001'
    UNION ALL SELECT 'Riscos Operacionais', 'Operação Empresarial Plus', 'RO-001'
    UNION ALL SELECT 'Riscos de Engenharia', 'Obra Segura', 'ENG-001'
) AS v
JOIN insurance_branches ib
    ON LOWER(ib.name) = LOWER(v.branch_name)
WHERE NOT EXISTS (
    SELECT 1
    FROM insurance_products ip
    WHERE ip.branch_id = ib.id
      AND LOWER(ip.product_code) = LOWER(v.product_code)
);
