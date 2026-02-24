"""
cross_verify.py — Cross-node integrity verification for multi-bank settlement.

Compares hash chains across all 6 banking nodes to detect:
  - Hash chain breaks (single-node tamper detection)
  - Missing settlement entries (deleted transactions)
  - Amount mismatches (modified transactions)
  - Orphan entries (fabricated transactions)

The clearing house chain is the authoritative record. When bank chains
disagree with clearing, the clearing chain is treated as ground truth.

Dependencies: integrity.py (for per-chain verification), bridge.py (for node access)
"""

import re
import sqlite3
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
from .bridge import COBOLBridge


@dataclass
class SettlementMatch:
    """Result of cross-referencing one settlement across nodes."""
    settlement_ref: str
    status: str            # "MATCHED" | "PARTIAL" | "MISMATCH" | "ORPHAN"
    amount: float
    source_bank: str
    dest_bank: str
    source_entry_found: bool
    clearing_entries_found: int  # 0, 1, or 2
    dest_entry_found: bool
    discrepancies: List[str] = field(default_factory=list)


@dataclass
class VerificationReport:
    """Complete cross-node verification results."""
    timestamp: str

    # Per-chain hash integrity (cryptographic linkage only)
    chain_integrity: Dict[str, bool]
    chain_lengths: Dict[str, int]

    # Balance reconciliation (DAT vs DB — separate from chain integrity)
    balance_drift: Dict[str, List[str]]

    # Cross-node settlement matching
    settlements_checked: int
    settlements_matched: int
    settlements_partial: int
    settlements_mismatched: int
    settlements_orphaned: int
    settlement_details: List[SettlementMatch]

    # Summary
    all_chains_intact: bool
    all_settlements_matched: bool
    anomalies: List[str]

    # Performance
    verification_time_ms: float


class CrossNodeVerifier:
    """Cross-node integrity verification engine."""

    NODES = ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']

    def __init__(self, data_dir: str = "banks"):
        """Load all 6 node bridges."""
        self.data_dir = data_dir
        self.bridges = {}
        for node in self.NODES:
            self.bridges[node] = COBOLBridge(node=node, data_dir=data_dir)

    def verify_all(self) -> VerificationReport:
        """
        Full cross-node verification:
        1. Verify each chain's hash integrity independently
        2. Extract all settlement references
        3. Cross-reference entries across chains
        4. Report anomalies
        """
        start_time = datetime.now()

        # Step 1: Per-chain hash integrity
        chain_integrity = {}
        chain_lengths = {}
        anomalies = []

        for node in self.NODES:
            result = self.bridges[node].chain.verify_chain()
            chain_integrity[node] = result['valid']
            chain_lengths[node] = result['entries_checked']
            if not result['valid']:
                anomalies.append(
                    f"{node} chain hash mismatch at entry #{result['first_break']} "
                    f"({result['break_type']})"
                )

        # Step 1b: Load all chain entries (needed for balance check and cross-ref)
        all_entries = {}
        for node in self.NODES:
            entries = self._get_chain_entries_with_details(node)
            all_entries[node] = entries

        # Step 1c: Balance reconciliation — separate from chain integrity
        # Balance drift is expected during simulation (internal activity changes
        # DAT balances without updating stale DB snapshots). This is informational,
        # NOT a chain integrity failure.
        balance_drift = {}
        for node in self.NODES:
            balance_issues = self._check_balance_reconciliation(node, all_entries.get(node, []))
            if balance_issues:
                balance_drift[node] = balance_issues

        # Step 2: Extract all settlement references from all chains

        # Step 3: Cross-reference settlements
        settlement_refs = set()
        for node, entries in all_entries.items():
            for entry in entries:
                ref = self._extract_settlement_ref(entry.get('description', ''))
                if ref:
                    settlement_refs.add(ref)

        settlement_details = []
        matched = 0
        partial = 0
        mismatched = 0
        orphaned = 0

        for ref in sorted(settlement_refs):
            match = self._cross_reference_settlement(ref, all_entries)
            settlement_details.append(match)
            if match.status == "MATCHED":
                matched += 1
            elif match.status == "PARTIAL":
                partial += 1
                anomalies.extend(match.discrepancies)
            elif match.status == "MISMATCH":
                mismatched += 1
                anomalies.extend(match.discrepancies)
            elif match.status == "ORPHAN":
                orphaned += 1
                anomalies.extend(match.discrepancies)

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        return VerificationReport(
            timestamp=datetime.now().isoformat(),
            chain_integrity=chain_integrity,
            chain_lengths=chain_lengths,
            balance_drift=balance_drift,
            settlements_checked=len(settlement_refs),
            settlements_matched=matched,
            settlements_partial=partial,
            settlements_mismatched=mismatched,
            settlements_orphaned=orphaned,
            settlement_details=settlement_details,
            all_chains_intact=all(chain_integrity.values()),
            all_settlements_matched=(matched == len(settlement_refs)),
            anomalies=anomalies,
            verification_time_ms=elapsed_ms,
        )

    def _get_chain_entries_with_details(self, node: str) -> List[Dict[str, Any]]:
        """Get all chain entries with full details for a node."""
        db = self.bridges[node].db
        cursor = db.execute("""
            SELECT chain_index, tx_id, account_id, tx_type, amount,
                   timestamp, description, status, tx_hash, prev_hash
            FROM chain_entries
            ORDER BY chain_index
        """)
        return [
            {
                'chain_index': row[0],
                'tx_id': row[1],
                'account_id': row[2],
                'tx_type': row[3],
                'amount': row[4],
                'timestamp': row[5],
                'description': row[6],
                'status': row[7],
                'tx_hash': row[8],
                'prev_hash': row[9],
                'node': node,
            }
            for row in cursor.fetchall()
        ]

    def _extract_settlement_ref(self, description: str) -> Optional[str]:
        """Extract STL-YYYYMMDD-NNNNNN from a description string."""
        match = re.search(r'(STL-\d{8}-\d{6})', description)
        return match.group(1) if match else None

    def _cross_reference_settlement(self, ref: str, all_entries: Dict) -> SettlementMatch:
        """Cross-reference a single settlement across all nodes."""
        source_entry = None
        dest_entry = None
        clearing_entries = []

        for node, entries in all_entries.items():
            for entry in entries:
                desc = entry.get('description', '')
                if ref not in desc:
                    continue

                if 'XFER-TO-' in desc:
                    source_entry = entry
                elif 'XFER-FROM-' in desc:
                    dest_entry = entry
                elif 'SETTLE-' in desc:
                    clearing_entries.append(entry)

        # Determine source and dest banks
        source_bank = source_entry['node'] if source_entry else ''
        dest_bank = dest_entry['node'] if dest_entry else ''
        amount = source_entry['amount'] if source_entry else (
            dest_entry['amount'] if dest_entry else (
                clearing_entries[0]['amount'] if clearing_entries else 0.0
            )
        )

        # Check completeness
        discrepancies = []
        has_source = source_entry is not None
        has_dest = dest_entry is not None
        num_clearing = len(clearing_entries)

        if has_source and has_dest and num_clearing == 2:
            # Check amount consistency
            amounts = {source_entry['amount'], dest_entry['amount']}
            amounts.update(e['amount'] for e in clearing_entries)
            if len(amounts) == 1:
                status = "MATCHED"
            else:
                status = "MISMATCH"
                discrepancies.append(
                    f"Amount mismatch for {ref}: source={source_entry['amount']}, "
                    f"dest={dest_entry['amount']}, clearing={[e['amount'] for e in clearing_entries]}"
                )
        elif has_source or has_dest or num_clearing > 0:
            missing = []
            if not has_source:
                missing.append("source bank entry")
            if not has_dest:
                missing.append("dest bank entry")
            if num_clearing < 2:
                missing.append(f"clearing entries ({num_clearing}/2)")
            status = "PARTIAL"
            discrepancies.append(f"Incomplete settlement {ref}: missing {', '.join(missing)}")
        else:
            status = "ORPHAN"
            discrepancies.append(f"Orphan settlement reference {ref}: no entries found")

        return SettlementMatch(
            settlement_ref=ref,
            status=status,
            amount=amount,
            source_bank=source_bank,
            dest_bank=dest_bank,
            source_entry_found=has_source,
            clearing_entries_found=num_clearing,
            dest_entry_found=has_dest,
            discrepancies=discrepancies,
        )

    def _check_balance_reconciliation(self, node: str, chain_entries: List[Dict]) -> List[str]:
        """
        Compare current ACCOUNTS.DAT balances against the SQLite accounts table.

        The accounts table was populated by _sync_accounts_to_db() which reads
        COBOL's ACCOUNTS LIST output (or the DAT file directly). After settlement,
        the bridge updates the DB balance to match what COBOL reported.

        If someone tampers the DAT file directly (bypassing COBOL and the chain),
        the DAT balance will diverge from the DB balance. This check catches that.
        """
        issues = []
        bridge = self.bridges[node]

        # Get current balances from ACCOUNTS.DAT (raw file read)
        current_accounts = bridge.load_accounts_from_dat()
        if not current_accounts:
            return issues

        # Get last-known balances from SQLite (synced after each COBOL operation)
        db_accounts = {}
        try:
            cursor = bridge.db.execute("SELECT id, balance FROM accounts")
            for row in cursor.fetchall():
                db_accounts[row[0].strip()] = row[1]
        except Exception:
            return issues

        # Compare DAT file balance vs DB balance for each account
        for acct in current_accounts:
            acct_id = acct['id']
            dat_balance = acct['balance']
            db_balance = db_accounts.get(acct_id)

            if db_balance is None:
                continue  # Account not tracked in DB

            if abs(dat_balance - db_balance) > 0.01:
                # Count chain entries for context
                tx_count = sum(
                    1 for entry in chain_entries
                    if entry['account_id'].strip() == acct_id
                )
                issues.append(
                    f"{node} balance tamper detected: {acct_id} "
                    f"DAT=${dat_balance:.2f} expected=${db_balance:.2f} "
                    f"(chain records {tx_count} transactions)"
                )

        return issues

    def find_settlement_entries(self, settlement_ref: str) -> Dict:
        """Find all entries related to a settlement reference across all chains."""
        all_entries = {}
        for node in self.NODES:
            all_entries[node] = self._get_chain_entries_with_details(node)
        return self._cross_reference_settlement(settlement_ref, all_entries)

    def close(self):
        """Close all bridge connections."""
        for bridge in self.bridges.values():
            bridge.close()


def tamper_balance(data_dir: str, node: str, account_id: str, new_amount: float):
    """
    DEMO ONLY: Directly modify an account balance in the .DAT file.
    Bypasses COBOL and the integrity chain, creating a detectable discrepancy.
    """
    dat_file = Path(data_dir) / node / "ACCOUNTS.DAT"
    if not dat_file.exists():
        raise FileNotFoundError(f"{dat_file} not found")

    # Read all records
    with open(dat_file, 'rb') as f:
        lines = f.readlines()

    # Find and modify the target account
    modified = False
    for i, line in enumerate(lines):
        line = line.rstrip(b'\n\r')
        if len(line) < 70:
            line = line.ljust(70)
        acct_id = line[0:10].decode('ascii').strip()
        if acct_id == account_id:
            # Build new balance bytes
            balance_int = int(abs(new_amount) * 100)
            balance_str = f"{balance_int:012d}"
            if new_amount < 0:
                balance_str = "-" + balance_str[1:]
            # Replace balance bytes (positions 41-53)
            new_line = line[:41] + balance_str.encode('ascii') + line[53:]
            lines[i] = new_line + b'\n'
            modified = True
            break

    if not modified:
        raise ValueError(f"Account {account_id} not found in {dat_file}")

    # Write back
    with open(dat_file, 'wb') as f:
        f.writelines(lines)

    return {
        'node': node,
        'account_id': account_id,
        'new_amount': new_amount,
        'file': str(dat_file),
    }
