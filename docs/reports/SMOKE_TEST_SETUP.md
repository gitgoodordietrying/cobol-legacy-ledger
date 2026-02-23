# Smoke Test Setup & Execution Guide

**Status**: GnuCOBOL not available on current dev environment. This guide is for running on your actual development system.

**Goal**: Compile SMOKETEST.cob, run it, observe the actual PIC S9(10)V99 balance format output, and validate the bridge parser against real COBOL output.

---

## Step 1: Install GnuCOBOL

### On Linux (Debian/Ubuntu)
```bash
sudo apt-get update
sudo apt-get install -y gnucobol

# Verify installation
cobc --version
```

### On macOS
```bash
brew install gnu-cobol

# Verify installation
cobc --version
```

### On Windows
**Option A: Use WSL (Windows Subsystem for Linux)** — Recommended
```bash
# Inside WSL Ubuntu terminal
sudo apt-get update
sudo apt-get install -y gnucobol
cobc --version
```

**Option B: Download Installer**
1. Visit https://gnucobol.sourceforge.io/
2. Download Windows binary distribution
3. Extract to a directory (e.g., `C:\gnucobol`)
4. Add to PATH: `C:\gnucobol\bin`
5. Verify: Open command prompt, type `cobc --version`

### On Docker (if preferred)
```bash
docker run -it --rm -v $(pwd):/work -w /work ubuntu:22.04 bash
apt-get update && apt-get install -y gnucobol
cobc --version
```

---

## Step 2: Prepare Project Directory

```bash
cd /path/to/cobol-legacy-ledger

# Ensure directory structure exists
mkdir -p cobol/bin
mkdir -p banks/BANK_A

# Verify SMOKETEST.cob and copybooks exist
ls -la cobol/src/SMOKETEST.cob
ls -la cobol/copybooks/ACCTREC.cpy
```

---

## Step 3: Compile SMOKETEST.cob

```bash
cd /path/to/cobol-legacy-ledger/cobol/src

# Compile with free-format and copybook path
cobc -x -free -I ../copybooks SMOKETEST.cob -o ../bin/SMOKETEST

# Verify binary was created
ls -la ../bin/SMOKETEST
```

**Expected**: Compilation succeeds with no warnings or errors.

---

## Step 4: Run SMOKETEST.cob

```bash
# Navigate to BANK_A data directory
cd /path/to/cobol-legacy-ledger/banks/BANK_A

# Run the smoke test
../../cobol/bin/SMOKETEST
```

**Expected Output** (capture this exactly):
```
OK|WRITE|ACT-T-001|Smoke Test User
OK|READ|ACT-T-001 |Smoke Test User               |C|??????|A|20260217|20260217
SMOKE-TEST|PASS|All checks succeeded
```

The `??????` is what we need to observe — the actual balance field representation from COBOL's DISPLAY of a PIC S9(10)V99 field.

---

## Step 5: Capture and Document Output

### Save the actual output to file
```bash
cd /path/to/cobol-legacy-ledger/banks/BANK_A

# Run test and capture output
../../cobol/bin/SMOKETEST > smoketest_output.txt 2>&1

# Display it
cat smoketest_output.txt
```

### Analyze the balance field
Look at the READ line. The balance field (marked with `|` delimiters) should show one of these formats:

**Expected format 1** (with literal decimal point):
```
00000012345.67
```
(13 characters: 10 digits + dot + 2 fractional)

**Expected format 2** (no literal decimal point):
```
000001234567
```
(12 characters: 10 digits + 2 fractional, no dot)

**Other possibilities**:
- Leading zeros might be replaced with spaces: `     12345.67`
- Sign indicator might appear: `+00000012345.67` or `-00000012345.67`
- Different alignment or padding

---

## Step 6: Create SMOKE_TEST_OBSERVATION.md

Create this file in the project root with your observations:

```bash
cat > SMOKE_TEST_OBSERVATION.md << 'EOF'
# Smoke Test Observation — 2026-02-18

## System Information
- OS: [Linux/macOS/Windows/etc]
- GnuCOBOL version: [output of `cobc --version`]
- Test date/time: [when you ran it]

## Compilation
```
[paste full cobc compilation output here]
```

## Execution Output
```
[paste full SMOKETEST.cob output here]
```

## Balance Format Analysis

### What we wrote in COBOL:
```cobol
MOVE 12345.67 TO ACCT-BALANCE  (PIC S9(10)V99)
DISPLAY ... ACCT-BALANCE ...
```

### What COBOL displayed:
```
00000012345.67
```
(length: 13 characters with dot)

OR

```
000001234567
```
(length: 12 characters, no dot)

### Character count and format:
- Field: ACCT-BALANCE
- PIC clause: S9(10)V99 (12 bytes storage: 10 digits + 2 fractional)
- Display format: [describe what you see]
- Character count: [count the exact characters in the balance field]
- Contains literal decimal point: [yes/no]
- Contains leading spaces: [yes/no]

## Parser Validation

### Current bridge.py parser implementation:
Located in `python/bridge.py`, method `_parse_balance()`:
```python
def _parse_balance(self, balance_bytes: bytes) -> float:
    balance_str = balance_bytes.decode('ascii').strip()
    if len(balance_str) == 12:
        integer_part = int(balance_str[:10])
        fraction_part = int(balance_str[10:12])
        balance = integer_part + (fraction_part / 100.0)
    else:
        # fallback parsing
        ...
```

### Does parser match actual output?
- [ ] Yes, parser correctly interprets the balance format
- [ ] No, parser needs adjustment for: [describe the mismatch]

### If adjustment needed:
Provide the corrected logic:
```python
# [corrected parser code here]
```

## Test Input vs. Test Output

| Field | Input | COBOL Display | Expected by Parser | Match? |
|-------|-------|---------------|--------------------|--------|
| ACCT-ID | ACT-T-001 | ACT-T-001 | ACT-T-001 | ✓ |
| ACCT-NAME | Smoke Test User | Smoke Test User | Smoke Test User | ✓ |
| ACCT-TYPE | C | C | C | ✓ |
| ACCT-BALANCE | 12345.67 | ? | 12345.67 | ? |
| ACCT-STATUS | A | A | A | ✓ |
| ACCT-OPEN-DATE | 20260217 | 20260217 | 20260217 | ✓ |
| ACCT-LAST-ACTIVITY | 20260217 | 20260217 | 20260217 | ✓ |

## Verdict
✓ Parser is correct and matches actual COBOL output
OR
✗ Parser needs adjustment (see details above)

---

*Created by smoke test observation on [date]*
EOF
cat SMOKE_TEST_OBSERVATION.md
```

---

## Step 7: Validate Parser Against Output

Once you have the actual output, test the bridge parser:

```python
from python.bridge import COBOLBridge

# Simulate the balance bytes from SMOKETEST.cob output
# If actual output was: 00000012345.67
balance_bytes = b'00000012345.67'

bridge = COBOLBridge(node="BANK_A")
parsed_balance = bridge._parse_balance(balance_bytes)

print(f"Input bytes: {balance_bytes}")
print(f"Parsed balance: {parsed_balance}")
print(f"Expected: 12345.67")
print(f"Match: {parsed_balance == 12345.67}")

bridge.close()
```

**Expected result**: `Match: True`

**If mismatch**: Update `bridge.py` `_parse_balance()` method to handle actual format.

---

## Step 8: Test Data Files

After smoke test, verify the data files:

```bash
# Check that TEST-ACCOUNTS.DAT was created
ls -la banks/BANK_A/TEST-ACCOUNTS.DAT

# Check the raw file content (70 bytes per record)
hexdump -C banks/BANK_A/TEST-ACCOUNTS.DAT | head -10

# Count bytes (should be multiple of 71 with newline)
wc -c banks/BANK_A/TEST-ACCOUNTS.DAT
```

---

## Troubleshooting

### Compilation error: "COPY statement failed"
```
Error: Cannot find copybook ACCTREC.cpy
```
**Fix**: Make sure you're in `cobol/src` directory and running:
```bash
cobc -x -free -I ../copybooks SMOKETEST.cob -o ../bin/SMOKETEST
```
The `-I ../copybooks` flag is critical.

### Compilation error: "Unrecognized option"
```
Error: unknown option '-free'
```
**Fix**: Your GnuCOBOL might be old. Try without `-free`:
```bash
cobc -x SMOKETEST.cob -o ../bin/SMOKETEST
```
(Though `-free` format is preferred for modern COBOL)

### Runtime error: "Cannot open file"
```
Error: Cannot open TEST-ACCOUNTS.DAT
```
**Fix**: Make sure you're in the `banks/BANK_A` directory when running:
```bash
cd /path/to/cobol-legacy-ledger/banks/BANK_A
../../cobol/bin/SMOKETEST
```

### Output shows garbage characters
```
OK|READ|ACT-T-001 |Smoke Test User               |C|▓▓▓▓▓|A|20260217|20260217
```
**Likely cause**: Character encoding issue. Try running with UTF-8:
```bash
LC_ALL=C.UTF-8 ../../cobol/bin/SMOKETEST
```

### FILE STATUS showing error
```
ERROR|FILE-OPEN-WRITE|35
```
**Likely cause**: Cannot write to directory. Make sure `banks/BANK_A` exists and is writable:
```bash
mkdir -p banks/BANK_A
chmod 755 banks/BANK_A
```

---

## Success Criteria

✓ **All of these must pass**:
1. `cobc --version` shows GnuCOBOL installed
2. `cobc -x -free -I ../copybooks SMOKETEST.cob` compiles without errors
3. `../../cobol/bin/SMOKETEST` runs without errors
4. Output shows all three lines (OK|WRITE, OK|READ, SMOKE-TEST|PASS)
5. Balance field in READ line matches expected format (13 chars with dot, or 12 without)
6. `_parse_balance()` test shows `Match: True`
7. `TEST-ACCOUNTS.DAT` exists and is 71 bytes (70 record + newline)
8. SMOKE_TEST_OBSERVATION.md documents everything

---

## Next Steps After Success

Once smoke test passes and parser is validated:

1. Create `SMOKE_TEST_OBSERVATION.md` in project root
2. Document the balance format
3. Update bridge parser if needed
4. Everything is unblocked for ACCOUNTS.cob implementation

---

## Reference: Expected SMOKETEST.cob Output

**Scenario**: Test account with balance $12,345.67

**Expected output** (most likely):
```
OK|WRITE|ACT-T-001|Smoke Test User
OK|READ|ACT-T-001 |Smoke Test User               |C|00000012345.67|A|20260217|20260217
SMOKE-TEST|PASS|All checks succeeded
```

**Why this format**:
- WRITE line confirms record was written successfully
- READ line shows all fields from the account record:
  - ACCT-ID: "ACT-T-001 " (10 chars, left-aligned with space padding)
  - ACCT-NAME: "Smoke Test User" with right-padding to 30 chars
  - ACCT-TYPE: "C"
  - ACCT-BALANCE: "00000012345.67" (13 chars: 10 digits + dot + 2 fractional)
  - ACCT-STATUS: "A"
  - ACCT-OPEN-DATE: "20260217"
  - ACCT-LAST-ACTIVITY: "20260217"
- PASS line confirms all checks succeeded

---

**You have everything you need. Run this on your system with cobc installed, capture the output, and we'll validate the parser. Then Phase 2 COBOL implementation is fully unblocked.**

