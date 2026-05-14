-- Test accounts for each role
-- Run this SQL in your database

-- Superadmin (role_id = 1) - Full access to everything
INSERT INTO employee (id, email_address, first_name, last_name, role_id, system_password, register_date, birth_date, sex, marital_stat)
VALUES (
    'EMP001',
    'superadmin@company.com',
    'Super',
    'Admin',
    1,
    'admin123',
    NOW(),
    '1990-01-01',
    'Male',
    'Single'
);

-- Finance (role_id = 2) - Can approve, disapprove, release. Cannot generate, modify, finalize, delete
INSERT INTO employee (id, email_address, first_name, last_name, role_id, system_password, register_date, birth_date, sex, marital_stat)
VALUES (
    'EMP002',
    'finance@company.com',
    'Finance',
    'User',
    2,
    'finance123',
    NOW(),
    '1990-01-01',
    'Male',
    'Single'
);

-- HR (role_id = 3) - Can generate, modify, add additionals, delete. Cannot finalize, approve, disapprove, release
INSERT INTO employee (id, email_address, first_name, last_name, role_id, system_password, register_date, birth_date, sex, marital_stat)
VALUES (
    'EMP003',
    'hr@company.com',
    'HR',
    'User',
    3,
    'hr123',
    NOW(),
    '1990-01-01',
    'Male',
    'Single'
);
