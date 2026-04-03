"""Export knowledge base to static JSON for the web console."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from python.cobol_analyzer.knowledge_base import ENTRIES

# Export existing entries
entries = []
for key, e in ENTRIES.items():
    entries.append({
        "name": e.name,
        "category": e.category,
        "era": e.era,
        "purpose": e.purpose,
        "mainframe_context": e.mainframe_context,
        "modern_equivalent": e.modern_equivalent,
        "example": e.example,
        "risk": e.risk,
    })

# Add new entries to reach 30+
new_entries = [
    {
        "name": "MOVE truncation",
        "category": "data",
        "era": "COBOL-68",
        "purpose": "COBOL MOVE silently truncates data that does not fit the receiving field. Alphanumeric MOVEs are left-justified and right-truncated; numeric MOVEs are right-justified and left-truncated.",
        "mainframe_context": "Fixed-length fields are fundamental to COBOL. Every field has an exact byte size defined by its PIC clause. MOVE does not raise errors -- it truncates to fit. MOVE CORRESPONDING matches fields by name between groups; renaming a field silently drops it.",
        "modern_equivalent": "Type-safe assignment with explicit casting. Runtime exceptions on overflow.",
        "example": "MOVE 1000005 TO PIC-FIELD.\n*> PIC 9(6) stores 000005 -- the leading 1 vanishes\n*> PIC X(4) receiving \"COBOL\" stores \"COBO\"",
        "risk": "High-order digits vanish without any error or warning. Group MOVEs lose decimal alignment because they are treated as alphanumeric regardless of subordinate types.",
    },
    {
        "name": "EBCDIC collating sequence",
        "category": "data",
        "era": "1964-present",
        "purpose": "EBCDIC sorts lowercase before uppercase before digits: a < A < 1. ASCII reverses this: 1 < A < a.",
        "mainframe_context": "IBM mainframes use EBCDIC natively. All SORT operations, SEARCH ALL binary searches, and IF comparisons use the platform collating sequence. Programs migrated from z/OS to ASCII platforms produce different sort orders.",
        "modern_equivalent": "Unicode with locale-aware collation (Collator in Java, locale.strxfrm in Python).",
        "example": "SORT SORT-FILE ON ASCENDING KEY MERCH-ID.\n*> EBCDIC: \"abc\" < \"ABC\" < \"123\"\n*> ASCII:  \"123\" < \"ABC\" < \"abc\"",
        "risk": "SEARCH ALL on a table sorted in EBCDIC order produces wrong results on ASCII. Every missed instance is a silent migration bug.",
    },
    {
        "name": "FILE STATUS codes",
        "category": "data",
        "era": "COBOL-68",
        "purpose": "Two-character code returned after every file I/O operation. Must be PIC X(2) not PIC 99.",
        "mainframe_context": "The five codes every banking COBOL programmer memorizes: 00=success, 10=end of file, 22=duplicate key, 23=record not found, 35=file not found at OPEN (typically missing DD in JCL).",
        "modern_equivalent": "Exception handling with specific exception types (FileNotFoundError, DuplicateKeyError).",
        "example": "SELECT ACCT-FILE ASSIGN TO \"ACCOUNTS.DAT\"\n    FILE STATUS IS WS-FS.\n...\nREAD ACCT-FILE.\nIF WS-FS NOT = \"00\" DISPLAY \"FAIL: \" WS-FS.",
        "risk": "Unchecked FILE STATUS means errors propagate silently. A failed READ returns stale data from the previous successful read.",
    },
    {
        "name": "Overpunch sign encoding",
        "category": "data",
        "era": "1964-present",
        "purpose": "Signed DISPLAY fields encode the sign in the zone nibble of the last byte. -123 in PIC S9(3) displays as '12L'.",
        "mainframe_context": "In EBCDIC: positive 0-9 map to {,A-I (zone C); negatives to },J-R (zone D). ASCII Micro Focus uses 0x70 zone (p-y). A character translation CORRUPTS signed fields.",
        "modern_equivalent": "Explicit sign representation (negative numbers have a - prefix).",
        "example": "*> PIC S9(3) DISPLAY format:\n*>   +123 stored as hex F1 F2 C3\n*>   -123 stored as hex F1 F2 D3 (displays as '12L')",
        "risk": "Python parsers must handle overpunch explicitly or every negative value becomes garbage.",
    },
    {
        "name": "SPACES vs LOW-VALUES vs HIGH-VALUES",
        "category": "data",
        "era": "COBOL-68",
        "purpose": "Figurative constants with specific hex values. SPACES=X'40'(EBCDIC)/X'20'(ASCII). LOW-VALUES=X'00'. HIGH-VALUES=X'FF'.",
        "mainframe_context": "LOW-VALUES is the minimum collating value. HIGH-VALUES is the maximum. A field initialized to LOW-VALUES does NOT equal SPACES.",
        "modern_equivalent": "null/None (LOW-VALUES), empty string (SPACES), MAX_VALUE sentinel (HIGH-VALUES).",
        "example": "MOVE LOW-VALUES TO WS-RECORD.\nIF WS-RECORD = SPACES  *> FALSE!",
        "risk": "Moving LOW-VALUES to a numeric field then performing arithmetic triggers S0C7 data exception abend.",
    },
    {
        "name": "Working-Storage persistence",
        "category": "mainframe",
        "era": "1970s-present",
        "purpose": "In batch, Working-Storage persists throughout execution. In CICS, each task gets a fresh copy.",
        "mainframe_context": "CICS pseudo-conversational: between interactions, the program ends and restarts. WS resets. State goes through COMMAREA (max 32,763 bytes) or Channels/Containers (CICS TS 3.1+).",
        "modern_equivalent": "Session state in web applications (cookies, session storage, database-backed sessions).",
        "example": "*> BATCH: WS-COUNTER persists across records\n*> CICS:  WS-COUNTER resets between transactions",
        "risk": "Converting batch to online without handling WS persistence leaves stale values. The #1 source of intermittent bugs in online COBOL.",
    },
    {
        "name": "Copybook dependency chains",
        "category": "mainframe",
        "era": "All eras",
        "purpose": "Copybooks are the schema. Changing a field requires recompiling ALL including programs -- miss one and you get silent field misalignment.",
        "mainframe_context": "One change can affect 50-200 programs. No dependency tracking beyond grep and tribal knowledge. Over 70% of business rules in legacy systems exist only in the code.",
        "modern_equivalent": "Schema migration tools (Flyway, Alembic) with automated dependency tracking.",
        "example": "COPY \"EMPREC.cpy\".\n*> Used by: PAYROLL, TAXCALC, DEDUCTN, PAYBATCH\n*> Change EMP-SALARY PIC -> recompile ALL FOUR",
        "risk": "Programs with stale copybook versions read data with wrong field boundaries. Wrong numbers that look plausible.",
    },
    {
        "name": "Y2K windowing",
        "category": "mainframe",
        "era": "1999-2050",
        "purpose": "Interprets 2-digit years using a pivot: IF YY >= 40 THEN 19XX ELSE 20XX. The pivot determines the cutoff.",
        "mainframe_context": "Full conversion was too expensive. Windowing deferred the problem ~50 years. IBM YEARWINDOW compiler option. Windows are now expiring.",
        "modern_equivalent": "Use 4-digit years. The Y2K problem was deferred, not solved.",
        "example": "IF WS-YY >= 50\n    MOVE 19 TO WS-CC\nELSE\n    MOVE 20 TO WS-CC.\n*> 2050 is interpreted as 1950!",
        "risk": "30-year mortgages from 2020 mature in 2050, crossing the pivot boundary. Practitioners report already encountering date problems.",
    },
    {
        "name": "Fixed-point arithmetic (banking)",
        "category": "banking",
        "era": "All eras",
        "purpose": "COMP-3 stores exact decimal values. 0.1 + 0.2 = 0.3 exactly, unlike IEEE 754.",
        "mainframe_context": "IBM z-Series has native BCD instructions making COMP-3 ~7-10x faster than binary. PIC S9(13)V99 COMP-3 = 8 bytes, up to +/-$999 trillion. The banking standard.",
        "modern_equivalent": "Python decimal.Decimal, Java BigDecimal, or integer-cents representation.",
        "example": "05 AMOUNT PIC S9(13)V99 COMP-3.\n*> 8 bytes, exact decimal, no IEEE 754 errors",
        "risk": "Using COMP-1/COMP-2 (floating point) for financial amounts introduces representation errors.",
    },
    {
        "name": "Day-count conventions",
        "category": "banking",
        "era": "Banking standard",
        "purpose": "Methods for counting days in interest: 30/360 (bonds), Actual/360 (money markets), Actual/365 (UK), Actual/Actual (Treasuries).",
        "mainframe_context": "30/360 assumes 30-day months. Actual/360 uses actual days over 360-day year -- charges ~5 extra days annually. All arithmetic uses INTEGER-OF-DATE and COMP-3.",
        "modern_equivalent": "Date libraries with explicit day-count parameters (QuantLib, Apache Commons DayCount).",
        "example": "*> 30/360: Feb has 30 days\n*> Actual/360: Feb has 28/29 days, denom 360\n*> Difference on $1M at 5%: ~$694/year",
        "risk": "Wrong convention on a 30-year mortgage changes total interest by thousands of dollars.",
    },
    {
        "name": "Regulatory compliance (CTR/SAR)",
        "category": "banking",
        "era": "BSA 1970, PATRIOT Act 2001",
        "purpose": "Mandatory reporting: CTR for cash > $10K, SAR for structuring patterns, OFAC for sanctions screening.",
        "mainframe_context": "Nightly batch detects: CTR (same-day cash > $10K, filed within 15 days), SAR (sub-$10K structuring, velocity anomalies, filed within 30 days), OFAC (SDN list fuzzy matching). SWIFT MT103/MT202/MT940 transitioning to ISO 20022.",
        "modern_equivalent": "Automated compliance engines with real-time screening and regulatory reporting pipelines.",
        "example": "*> CTR: IF DAILY-CASH > 10000\n*> SAR: IF TXN-COUNT > 5 AND EACH < 10000\n*> OFAC: fuzzy match against SDN list",
        "risk": "Missing a CTR/SAR filing is a federal crime. The $10K threshold unchanged since 1970.",
    },
    {
        "name": "DB2 embedded SQL",
        "category": "mainframe",
        "era": "1983-present",
        "purpose": "EXEC SQL...END-EXEC embeds SQL in COBOL. Host variables prefixed with : pass data between COBOL and DB2.",
        "mainframe_context": "DCLGEN generates copybooks from DB2 tables. Indicator variables (PIC S9(4) COMP) signal NULLs (-1). SQLCA codes: 0=success, +100=not found, -803=duplicate, -811=multiple rows. In CICS, use SYNCPOINT for commits.",
        "modern_equivalent": "ORM (SQLAlchemy, Hibernate) or prepared statements with parameterized queries.",
        "example": "EXEC SQL\n    SELECT NAME INTO :WS-NAME\n    FROM ACCOUNTS WHERE ID = :WS-ID\nEND-EXEC.\nIF SQLCODE = +100 DISPLAY \"NOT FOUND\".",
        "risk": "EXEC SQL is the primary migration blocker from IBM to GnuCOBOL.",
    },
    {
        "name": "GnuCOBOL compatibility",
        "category": "dialect",
        "era": "2000s-present",
        "purpose": "Open-source COBOL compiler passing 9,700+ of 9,748 NIST tests. Translates COBOL to C to native binary via GCC.",
        "mainframe_context": "Dialect flags: -std=ibm, -std=mf, -std=cobol2014. COMP-3 byte-identical (critical win). COMP-1/COMP-2 incompatible (hex float vs IEEE 754). EXEC CICS requires middleware replacement.",
        "modern_equivalent": "Cross-compilation tools, compatibility shims, platform abstraction layers.",
        "example": "cobc -x -free -std=ibm -I copybooks PAYROLL.cob\n*> Produces native executable via GCC",
        "risk": "EXEC CICS not supported. EBCDIC-to-ASCII corrupts signed DISPLAY. Hex literals change meaning. JCL must become shell scripts.",
    },
]

all_entries = entries + new_entries
output = {"version": "1.0", "count": len(all_entries), "entries": all_entries}

outpath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "console", "data", "knowledge-base.json")
with open(outpath, "w") as f:
    json.dump(output, f, indent=2)

print(f"Written {len(all_entries)} entries to {outpath}")
