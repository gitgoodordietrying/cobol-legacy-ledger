# SMOKETEST.cob Output Observation

**Date**: 2026-02-18
**Status**: ✅ OBSERVATION COMPLETE
**Critical for**: bridge.py balance parser validation

---

## SMOKETEST Execution Result

```bash
$ cd banks/BANK_A && /app/cobol/bin/SMOKETEST

OK|WRITE|ACT-T-001|Smoke Test User
OK|READ|ACT-T-001 |Smoke Test User               |C|+0000012345.67|A|20260217|20260217
SMOKE-TEST|PASS|All checks succeeded
```

---

## Balance Format Analysis

### Test Value Created
- **Created as**: `PIC S9(10)V99` with value `12345.67`
- **Written to ACCTREC file**: Fixed-width 70-byte record

### Balance as Displayed
```
+0000012345.67
```

### Format Breakdown
| Component | Value | Chars | Notes |
|-----------|-------|-------|-------|
| Sign | `+` | 1 | S in PIC S9(10)V99 generates sign |
| Integer part | `0000012345` | 10 | PIC 9(10) |
| Decimal point | `.` | 1 | **Literal dot** (GnuCOBOL renders V as dot) |
| Decimal part | `67` | 2 | PIC 99 |
| **Total** | | **14 chars** | **KEY FINDING** |

---

## Critical Discovery: Decimal Point Representation

**GnuCOBOL Behavior:**
- `PIC S9(10)V99` is stored as 12 bytes (1 sign byte + 10 int + 1 implicit decimal flag + 2 decimal)
- When DISPLAYED to stdout, GnuCOBOL renders the **implicit decimal (V) as a literal period**
- Output format: `{SIGN}{10-DIGIT-INT}.{2-DIGIT-DECIMAL}`

**Example:** Test value 12345.67
- Storage: 12 bytes (binary-coded)
- Display: `+0000012345.67` (14 characters)

---

## Impact on bridge.py Parser

### Current Parser Assumption
The bridge.py balance parser (in `integrity.py` and `bridge.py`) currently assumes:
```python
# Assumed: 12 ASCII characters, no decimal point
balance_str = "000001542050"  # 12 chars for $15,420.50
balance = int(balance_str) / 100  # Divide by 100 to get decimal places
# Result: 15420.50
```

### Required Parser Update
The actual format is **14 characters with a literal decimal point**:
```python
# Actual COBOL output
balance_str = "+0000015420.50"  # 14 chars with sign and period

# Corrected parser logic
balance_str = balance_str.replace('+', '').replace('-', '')  # Remove sign
balance_str = balance_str.replace('.', '')  # Remove period
balance = int(balance_str) / 100  # Same division logic
# Result: 15420.50
```

Or more directly:
```python
# Parse directly from display format
balance_float = float(balance_str)  # "+0000015420.50" → 15420.50
```

---

## ACCTREC Record Structure (Verified)

From the READ output line:
```
OK|READ|ACT-T-001 |Smoke Test User               |C|+0000012345.67|A|20260217|20260217
```

Parsed against ACCTREC.cpy layout:
```cobol
01  ACCOUNT-RECORD.
    05  ACCT-ID              PIC X(10).         → "ACT-T-001 " (10 chars, right-padded)
    05  ACCT-NAME            PIC X(30).         → "Smoke Test User               " (30 chars)
    05  ACCT-TYPE            PIC X(1).          → "C" (Checking)
    05  ACCT-BALANCE         PIC S9(10)V99.     → "+0000012345.67" (14 chars when displayed)
    05  ACCT-STATUS          PIC X(1).          → "A" (Active)
    05  ACCT-OPEN-DATE       PIC 9(8).          → "20260217" (Feb 17, 2026)
    05  ACCT-LAST-ACTIVITY   PIC 9(8).          → "20260217"
```

**Record total (as displayed)**: 10 + 30 + 1 + 14 + 1 + 8 + 8 = **72 characters**

**Record storage (binary)**: 10 + 30 + 1 + 12 + 1 + 8 + 8 = **70 bytes** ✓

The discrepancy (72 vs 70) is because BALANCE is stored as 12 bytes but displays as 14 characters.

---

## Parser Validation Checklist

- [ ] **Task 1**: Update `python/integrity.py` balance parsing
  - [ ] Handle sign character (+/-)
  - [ ] Handle literal decimal point
  - [ ] Test with actual SMOKETEST output

- [ ] **Task 2**: Update `python/bridge.py` balance parsing
  - [ ] Update `parse_acctrec()` method
  - [ ] Verify against 70-byte fixed-width format
  - [ ] Test with seeded ACCOUNTS.DAT

- [ ] **Task 3**: Run full bridge test
  - [ ] `test_bridge.py` must pass with new parser
  - [ ] Verify all 6 nodes parse correctly
  - [ ] Confirm account counts match expected

- [ ] **Task 4**: Update `test_bridge.py` test data
  - [ ] Use realistic balance format (+/-000XXXXXXXX.XX)
  - [ ] Test edge cases (negative balances, zeros)
  - [ ] Test all account types (checking, savings)

---

## Next Steps

1. **Immediate**: Update bridge.py to handle `+0000XXXXXX.XX` format
2. **Test**: Run `test_bridge.py` with new parser
3. **Seed**: Create seeded ACCOUNTS.DAT for all 6 nodes
4. **Demo**: Run Phase 1 demo showing account listing and balances
5. **Gate**: Verify Phase 1 gate check #3 passes (correct account counts)

---

## Files Affected by Parser Change

| File | Change | Impact |
|------|--------|--------|
| `python/bridge.py` | `parse_acctrec()` method | ⚠️ HIGH - Core parsing |
| `python/integrity.py` | Balance display formatting | ⚠️ MEDIUM - Demo output |
| `python/tests/test_bridge.py` | Test expectations | ⚠️ MEDIUM - Test data |
| `python/cli.py` | Display formatting | ⚠️ LOW - User output |

---

## Documentation

This observation unlocks Phase 1 → Phase 2 transition:
- ✅ COBOL compilation verified
- ✅ I/O correctness verified
- ✅ Balance format observed
- 🔄 Parser requires update
- ⏳ Phase 1 demo ready after parser fix

**Status**: Ready for bridge.py parser update
