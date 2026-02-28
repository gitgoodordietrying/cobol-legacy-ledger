"""Generate EMPLOYEES.DAT matching EMPREC.cpy 95-byte layout."""

employees = [
    # (ID, Name, Bank, Acct, Salary_cents, Hourly_cents, Hours, Periods, Status, PayType, TaxBracket, HireDate, Dept, Med, Dental, 401k_pct_x100)
    ('EMP-001', 'Alice Johnson', 'BANK_A', 'ACT-A-001', 7500000, 0, 0, 26, 'A', 'S', 1, '19950315', 'ACCT', 'B', 'N', 6),
    ('EMP-002', 'Bob Martinez', 'BANK_A', 'ACT-A-002', 0, 4520, 40, 26, 'A', 'H', 2, '20010820', 'WARH', 'N', 'Y', 3),
    ('EMP-003', 'Carol Williams', 'BANK_A', 'ACT-A-003', 8200000, 0, 0, 26, 'A', 'S', 1, '19980112', 'MGMT', 'P', 'Y', 8),
    ('EMP-004', 'David Chen', 'BANK_A', 'ACT-A-004', 0, 3850, 45, 26, 'A', 'H', 3, '20051103', 'OPSR', 'B', 'N', 5),
    ('EMP-005', 'Eve Santos', 'BANK_A', 'ACT-A-005', 6100000, 0, 0, 26, 'A', 'S', 1, '20100615', 'FINA', 'P', 'Y', 6),
    ('EMP-006', "Frank O'Brien", 'BANK_B', 'ACT-B-001', 9500000, 0, 0, 26, 'A', 'S', 1, '19920708', 'EXEC', 'B', 'N', 10),
    ('EMP-007', 'Grace Kim', 'BANK_B', 'ACT-B-002', 5600000, 0, 0, 26, 'A', 'S', 2, '20030422', 'ACCT', 'P', 'Y', 7),
    ('EMP-008', 'Henry Okafor', 'BANK_B', 'ACT-B-003', 0, 4100, 38, 26, 'A', 'H', 3, '20080914', 'OPSR', 'N', 'N', 4),
    ('EMP-009', 'Isabel Reyes', 'BANK_B', 'ACT-B-004', 7200000, 0, 0, 26, 'A', 'S', 1, '19990530', 'MGMT', 'B', 'N', 9),
    ('EMP-010', 'James Park', 'BANK_B', 'ACT-B-005', 0, 3200, 40, 26, 'T', 'H', 4, '20120101', 'TEMP', 'N', 'N', 0),
    ('EMP-011', 'Karen Schmidt', 'BANK_C', 'ACT-C-001', 6800000, 0, 0, 26, 'A', 'S', 1, '20000301', 'ACCT', 'P', 'Y', 6),
    ('EMP-012', 'Larry Thompson', 'BANK_C', 'ACT-C-002', 0, 4800, 42, 26, 'A', 'H', 2, '20060715', 'WARH', 'N', 'Y', 4),
    ('EMP-013', 'Maria Garcia', 'BANK_C', 'ACT-C-003', 11000000, 0, 0, 26, 'A', 'S', 1, '19880620', 'EXEC', 'P', 'Y', 10),
    ('EMP-014', 'Nathan Wright', 'BANK_C', 'ACT-C-004', 0, 3900, 40, 26, 'A', 'H', 3, '20091128', 'OPSR', 'B', 'N', 5),
    ('EMP-015', 'Olivia Davis', 'BANK_C', 'ACT-C-005', 5500000, 0, 0, 26, 'A', 'S', 2, '20140203', 'FINA', 'N', 'N', 7),
    ('EMP-016', 'Patrick Lee', 'BANK_D', 'ACT-D-001', 7800000, 0, 0, 26, 'A', 'S', 1, '19970412', 'ACCT', 'P', 'Y', 8),
    ('EMP-017', 'Quinn Foster', 'BANK_D', 'ACT-D-002', 0, 4200, 40, 26, 'A', 'H', 2, '20040818', 'WARH', 'N', 'Y', 3),
    ('EMP-018', 'Rachel Nguyen', 'BANK_D', 'ACT-D-003', 8900000, 0, 0, 26, 'A', 'S', 1, '19930925', 'MGMT', 'B', 'N', 9),
    ('EMP-019', 'Samuel Brown', 'BANK_D', 'ACT-D-004', 0, 3600, 40, 26, 'A', 'H', 3, '20070611', 'OPSR', 'N', 'N', 5),
    ('EMP-020', 'Tina Washington', 'BANK_D', 'ACT-D-005', 6300000, 0, 0, 26, 'A', 'S', 2, '20110509', 'FINA', 'P', 'Y', 6),
    ('EMP-021', 'Ulrich Bauer', 'BANK_E', 'ACT-E-001', 7100000, 0, 0, 26, 'A', 'S', 1, '19960827', 'ACCT', 'P', 'Y', 7),
    ('EMP-022', 'Victoria Patel', 'BANK_E', 'ACT-E-002', 5100000, 0, 0, 26, 'A', 'S', 2, '20020314', 'ACCT', 'B', 'N', 6),
    ('EMP-023', 'William Chang', 'BANK_E', 'ACT-E-003', 0, 4500, 40, 26, 'A', 'H', 3, '20100720', 'WARH', 'N', 'Y', 4),
    ('EMP-024', 'Xena Rodriguez', 'BANK_E', 'ACT-E-004', 9200000, 0, 0, 26, 'A', 'S', 1, '19910103', 'EXEC', 'P', 'Y', 10),
    ('EMP-025', 'Yuki Tanaka Sato', 'BANK_E', 'ACT-E-005', 0, 3400, 40, 26, 'L', 'H', 4, '20130605', 'OPSR', 'N', 'N', 3),
]

lines = []
for e in employees:
    eid, name, bank, acct, salary, hourly, hours, periods, status, paytype, bracket, hire, dept, med, dental, k401 = e
    f_id = eid.ljust(7)[:7]
    f_name = name.ljust(25)[:25]
    f_bank = bank.ljust(8)[:8]
    f_acct = acct.ljust(10)[:10]
    f_salary = f'{salary:09d}'
    f_hourly = f'{hourly:05d}'
    f_hours = f'{hours:04d}'
    f_periods = f'{periods:04d}'
    f_status = status
    f_paytype = paytype
    f_bracket = f'{bracket:02d}'
    f_hire = hire
    f_dept = dept.ljust(4)[:4]
    f_med = med
    f_dental = dental
    f_k401 = f'{k401:03d}'
    f_filler = '  '

    line = (f_id + f_name + f_bank + f_acct + f_salary + f_hourly +
            f_hours + f_periods + f_status + f_paytype + f_bracket +
            f_hire + f_dept + f_med + f_dental + f_k401 + f_filler)
    assert len(line) == 95, f'Line length {len(line)} for {eid}'
    lines.append(line)

with open('COBOL-BANKING/payroll/data/PAYROLL/EMPLOYEES.DAT', 'w', newline='\n') as f:
    for line in lines:
        f.write(line + '\n')

print(f'Generated {len(lines)} records, each 95 bytes')
r = lines[0]
print(f'ACCT: [{r[40:50]}] STATUS: [{r[72:73]}] TYPE: [{r[73:74]}]')
