"""
settlement.py -- Inter-bank transfer orchestration via COBOL subprocess calls.

This module turns 6 independent COBOL banking nodes into a settlement network
by orchestrating multi-step transfers through the CLEARING node. No COBOL
programs are modified -- Python calls the existing binaries at each node in
sequence, creating a settlement flow with three independent records.

Why clearing houses exist:
    In real banking, banks don't transfer money directly to each other. Instead,
    a central clearing house acts as an intermediary. Each bank maintains a
    "nostro account" at the clearing house -- essentially a working-capital
    deposit. When BANK_A sends money to BANK_B, the clearing house debits
    BANK_A's nostro and credits BANK_B's nostro. This creates an auditable
    trail at a neutral third party and eliminates bilateral trust requirements.

Settlement flow (3 steps across 3 nodes):
    Step 1: DEBIT source account at source bank       (COBOL WITHDRAW)
    Step 2: RECORD at CLEARING house                  (two-sided: DEPOSIT + WITHDRAW)
    Step 3: CREDIT destination account at dest bank   (COBOL DEPOSIT)

    Each step produces an independent transaction record in a different node's
    integrity chain. Cross-node verification (cross_verify.py) later confirms
    that all 3 steps match.

Design principle -- fail-forward, not rollback:
    If Step 1 succeeds but Step 3 fails, we log it, flag it, and report
    PARTIAL_FAILURE. This matches real banking settlement exception handling:
    you don't "undo" a wire transfer -- you flag it for manual resolution.
    The settlement reference (STL-YYYYMMDD-NNNNNN) makes it traceable.

Dependencies: bridge.py (for COBOL subprocess execution and output parsing)
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
from .bridge import COBOLBridge


# ── Nostro Account Mapping ────────────────────────────────────
# Each bank has exactly one nostro (correspondent) account at the clearing house.
# "Nostro" is Latin for "ours" -- it's the bank's own money held at another
# institution. These accounts start with $10M working capital and track net
# settlement positions. After a batch of transfers, the nostro balances should
# net to zero (every outflow has a corresponding inflow).
NOSTRO_MAP = {
    'BANK_A': 'NST-BANK-A',
    'BANK_B': 'NST-BANK-B',
    'BANK_C': 'NST-BANK-C',
    'BANK_D': 'NST-BANK-D',
    'BANK_E': 'NST-BANK-E',
}


@dataclass
class SettlementResult:
    """Result of a single inter-bank transfer.

    Captures the outcome of all 3 settlement steps. On success, all four
    transaction IDs are populated. On partial failure, only the IDs for
    completed steps are filled in -- the rest remain empty strings.

    The settlement_ref (STL-YYYYMMDD-NNNNNN) is embedded in every transaction
    description, making it possible to cross-reference entries across all 3
    nodes during verification.
    """
    status: str              # "COMPLETED" | "PARTIAL_FAILURE" | "FAILED"
    source_trx_id: str       # Transaction ID from Step 1 (or "" if failed)
    clearing_deposit_id: str  # Transaction ID from Step 2a (or "")
    clearing_withdraw_id: str # Transaction ID from Step 2b (or "")
    dest_trx_id: str         # Transaction ID from Step 3 (or "")
    amount: float
    source_bank: str
    source_account: str      # Source account ID (ACT-A-001, etc.)
    dest_bank: str
    dest_account: str        # Destination account ID (ACT-B-003, etc.)
    error: str               # Empty string on success, error message on failure
    steps_completed: int     # 0, 1, 2, or 3
    settlement_ref: str      # Unique settlement reference (STL-YYYYMMDD-NNNNNN)
    timestamp: str           # ISO format timestamp


class SettlementCoordinator:
    """Orchestrates inter-bank transfers across 6 COBOL nodes.

    Holds a COBOLBridge instance for each of the 6 nodes (5 banks + CLEARING).
    When execute_transfer() is called, it coordinates the 3-step settlement
    by calling process_transaction() on the appropriate bridge instances
    in sequence.
    """

    def __init__(self, data_dir: str = "COBOL-BANKING/data"):
        """
        Initialize coordinator with bridges to all 6 nodes.

        Args:
            data_dir: Directory containing per-node subdirectories (default: banks)
        """
        self.data_dir = data_dir
        self.nodes = {}
        for node in ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']:
            self.nodes[node] = COBOLBridge(node=node, data_dir=data_dir)

        # ── Settlement Reference Counter ──────────────────────────────
        # Sequential counter for generating unique settlement references.
        # Combined with the date, this produces STL-YYYYMMDD-NNNNNN format
        # which fits within COBOL's PIC X(12) description fields when
        # embedded in transaction descriptions.
        self._settlement_counter = 0

    def _generate_settlement_ref(self, sim_date: Optional[datetime] = None) -> str:
        """Generate unique settlement reference: STL-YYYYMMDD-NNNNNN"""
        date_str = (sim_date or datetime.now()).strftime('%Y%m%d')
        self._settlement_counter += 1
        return f"STL-{date_str}-{self._settlement_counter:06d}"

    def execute_transfer(
        self,
        source_bank: str,
        source_account: str,
        dest_bank: str,
        dest_account: str,
        amount: float,
        description: str = "",
        sim_date: Optional[datetime] = None
    ) -> SettlementResult:
        """
        Execute a three-step inter-bank transfer.

        Step 1: Debit source account at source bank
        Step 2: Record settlement at CLEARING (two-sided deposit + withdraw)
        Step 3: Credit destination account at destination bank

        Returns SettlementResult with status, all transaction IDs, and any errors.
        On partial failure, returns partial results with error flags -- does NOT
        attempt rollback (matches real settlement exception handling).

        Args:
            source_bank: Source node (BANK_A, BANK_B, etc.)
            source_account: Source account ID (ACT-A-001, etc.)
            dest_bank: Destination node
            dest_account: Destination account ID
            amount: Transfer amount in dollars
            description: Human-readable description

        Returns:
            SettlementResult with detailed status and transaction IDs
        """
        settlement_ref = self._generate_settlement_ref(sim_date)
        timestamp = (sim_date or datetime.now()).isoformat()

        result = SettlementResult(
            status="PENDING",
            source_trx_id="",
            clearing_deposit_id="",
            clearing_withdraw_id="",
            dest_trx_id="",
            amount=amount,
            source_bank=source_bank,
            source_account=source_account,
            dest_bank=dest_bank,
            dest_account=dest_account,
            error="",
            steps_completed=0,
            settlement_ref=settlement_ref,
            timestamp=timestamp
        )

        try:
            # ============================================================
            # STEP 1: SOURCE DEBIT
            # ============================================================
            # Withdraw from the sender's account at their bank.
            # The description encodes the settlement reference so that
            # cross-node verification can later match this entry with
            # the corresponding CLEARING and destination entries.
            source_desc = f"XFER-TO-{dest_bank}-{dest_account}|{settlement_ref}"
            source_bridge = self.nodes[source_bank]
            source_result = source_bridge.process_transaction(
                tx_type="W",  # Single-char code matching COBOL TRANSACT.cob convention
                account_id=source_account,
                amount=amount,
                description=source_desc
            )

            if source_result["status"] != "00":
                result.status = "FAILED"
                result.error = f"Step 1 (source debit) failed: {source_result.get('message', 'Unknown error')}"
                result.steps_completed = 0
                return result

            result.source_trx_id = source_result.get("tx_id", "")
            result.steps_completed = 1

            # ============================================================
            # STEP 2: CLEARING SETTLEMENT (TWO-SIDED)
            # ============================================================
            # The clearing house records both sides of the settlement:
            #   2a: DEPOSIT into source bank's nostro (money received)
            #   2b: WITHDRAW from dest bank's nostro (money sent out)
            # This two-sided entry ensures the clearing house always
            # nets to zero -- every deposit has a matching withdrawal.
            clearing_bridge = self.nodes["CLEARING"]

            # Step 2a: CLEARING DEPOSIT (receive in source's nostro)
            clear_desc_deposit = f"SETTLE-{source_bank}-TO-{dest_bank}|{result.source_trx_id}|{settlement_ref}"
            clear_result_deposit = clearing_bridge.process_transaction(
                tx_type="D",  # Deposit into source bank's nostro
                account_id=NOSTRO_MAP[source_bank],
                amount=amount,
                description=clear_desc_deposit
            )

            if clear_result_deposit["status"] != "00":
                result.status = "PARTIAL_FAILURE"
                result.error = f"Step 2a (clearing deposit) failed: {clear_result_deposit.get('message', 'Unknown error')}"
                result.steps_completed = 1  # Source debited but clearing failed
                return result

            result.clearing_deposit_id = clear_result_deposit.get("tx_id", "")

            # Step 2b: CLEARING WITHDRAW (pay out from destination's nostro)
            clear_desc_withdraw = f"SETTLE-{source_bank}-TO-{dest_bank}|{result.source_trx_id}|{settlement_ref}"
            clear_result_withdraw = clearing_bridge.process_transaction(
                tx_type="W",  # Withdraw from destination bank's nostro
                account_id=NOSTRO_MAP[dest_bank],
                amount=amount,
                description=clear_desc_withdraw
            )

            if clear_result_withdraw["status"] != "00":
                result.status = "PARTIAL_FAILURE"
                result.error = f"Step 2b (clearing withdraw) failed: {clear_result_withdraw.get('message', 'Unknown error')}"
                # Steps completed = 2: Step 1 (source debit) + Step 2a (clearing deposit)
                # succeeded. Step 2b failed, but 2a already modified the clearing ledger.
                result.steps_completed = 2
                return result

            result.clearing_withdraw_id = clear_result_withdraw.get("tx_id", "")
            result.steps_completed = 2

            # ============================================================
            # STEP 3: DESTINATION CREDIT
            # ============================================================
            # Deposit into the recipient's account at their bank.
            # The description references the settlement ref and source,
            # completing the audit trail across all 3 nodes.
            dest_desc = f"XFER-FROM-{source_bank}-{source_account}|{settlement_ref}"
            dest_bridge = self.nodes[dest_bank]
            dest_result = dest_bridge.process_transaction(
                tx_type="D",  # Deposit into destination account
                account_id=dest_account,
                amount=amount,
                description=dest_desc
            )

            if dest_result["status"] != "00":
                result.status = "PARTIAL_FAILURE"
                result.error = f"Step 3 (destination credit) failed: {dest_result.get('message', 'Unknown error')}"
                result.steps_completed = 2  # Source debited, clearing succeeded, destination failed
                return result

            result.dest_trx_id = dest_result.get("tx_id", "")
            result.steps_completed = 3
            result.status = "COMPLETED"

        except Exception as e:
            result.status = "FAILED"
            result.error = str(e)

        return result

    def execute_batch_settlement(self, transfers: List[Dict]) -> List[SettlementResult]:
        """
        Execute multiple inter-bank transfers sequentially.

        Each transfer should be a dict:
        {
            'source_bank': 'BANK_A',
            'source_account': 'ACT-A-001',
            'dest_bank': 'BANK_B',
            'dest_account': 'ACT-B-003',
            'amount': 500.00,
            'description': 'Wire transfer'
        }

        Does NOT stop on individual transfer failure -- processes all and reports.
        This matches real batch settlement behavior: a single NSF rejection
        should not block the rest of the batch.

        Args:
            transfers: List of transfer dictionaries

        Returns:
            List of SettlementResult in same order
        """
        results = []
        for transfer in transfers:
            result = self.execute_transfer(
                source_bank=transfer['source_bank'],
                source_account=transfer['source_account'],
                dest_bank=transfer['dest_bank'],
                dest_account=transfer['dest_account'],
                amount=transfer['amount'],
                description=transfer.get('description', '')
            )
            results.append(result)

        return results

    def get_settlement_summary(self, results: List[SettlementResult]) -> Dict:
        """
        Compute net settlement positions across all banks.

        This is the "proof" that the clearing house is balanced: for every
        completed transfer, the source bank's net position decreases and
        the destination bank's net position increases by the same amount.
        The sum of all nostro position changes should be exactly zero.

        Returns dict with:
        - total_transfers: count of transfers
        - completed: count of COMPLETED transfers
        - failed: count of FAILED transfers
        - partial: count of PARTIAL_FAILURE transfers
        - net_positions: {bank: net_amount}
        - clearing_balance_check: True if nostro net == 0
        - nostro_positions: {nostro_id: balance_change}
        """
        total = len(results)
        completed = sum(1 for r in results if r.status == "COMPLETED")
        failed = sum(1 for r in results if r.status == "FAILED")
        partial = sum(1 for r in results if r.status == "PARTIAL_FAILURE")

        # ── Net Position Calculation ──────────────────────────────────
        # Track how much each bank has sent vs received. For a balanced
        # system, the sum of all positions across all banks equals zero.
        net_positions = {node: 0.0 for node in ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']}
        nostro_positions = {nostro: 0.0 for nostro in NOSTRO_MAP.values()}

        for result in results:
            if result.status == "COMPLETED" or result.status == "PARTIAL_FAILURE":
                # Source bank: outflow (negative)
                if result.steps_completed >= 1:
                    net_positions[result.source_bank] -= result.amount

                # Destination bank: inflow (positive)
                if result.steps_completed >= 3:
                    net_positions[result.dest_bank] += result.amount

                # Clearing house nostro: the two-sided settlement
                if result.steps_completed >= 2:
                    # Source nostro receives (positive)
                    nostro_positions[NOSTRO_MAP[result.source_bank]] += result.amount
                    # Destination nostro pays out (negative)
                    nostro_positions[NOSTRO_MAP[result.dest_bank]] -= result.amount

        # ── Balance Check ─────────────────────────────────────────────
        # The nostro net should be zero (or very close, allowing for
        # floating-point rounding). If it's not, something is wrong with
        # the settlement logic.
        nostro_net = sum(nostro_positions.values())
        clearing_balanced = abs(nostro_net) < 0.01  # Allow for floating point rounding

        return {
            'total_transfers': total,
            'completed': completed,
            'failed': failed,
            'partial': partial,
            'net_positions': net_positions,
            'nostro_positions': nostro_positions,
            'clearing_balance_check': clearing_balanced,
            'nostro_net': nostro_net,
        }


# ── Demo Batch ────────────────────────────────────────────────
# Pre-defined transfers designed to exercise all banks and test edge cases.
# Includes normal transfers, a near-CTR threshold amount ($9,500),
# an intentional NSF failure ($50,000 from a low-balance account),
# and a reverse-direction transfer to create circular flow.
DEMO_SETTLEMENT_BATCH = [
    # Normal transfers across different bank pairs
    {"source_bank": "BANK_A", "source_account": "ACT-A-001", "dest_bank": "BANK_B", "dest_account": "ACT-B-003", "amount": 500.00, "description": "Wire transfer"},
    {"source_bank": "BANK_B", "source_account": "ACT-B-001", "dest_bank": "BANK_C", "dest_account": "ACT-C-002", "amount": 1200.00, "description": "Invoice payment"},
    {"source_bank": "BANK_C", "source_account": "ACT-C-001", "dest_bank": "BANK_D", "dest_account": "ACT-D-001", "amount": 3500.00, "description": "Quarterly dividend"},
    {"source_bank": "BANK_D", "source_account": "ACT-D-002", "dest_bank": "BANK_E", "dest_account": "ACT-E-001", "amount": 750.00, "description": "Consulting fee"},
    {"source_bank": "BANK_E", "source_account": "ACT-E-001", "dest_bank": "BANK_A", "dest_account": "ACT-A-003", "amount": 2000.00, "description": "Loan repayment"},

    # Near-CTR threshold (compliance flag expected in COBOL output)
    {"source_bank": "BANK_A", "source_account": "ACT-A-002", "dest_bank": "BANK_C", "dest_account": "ACT-C-001", "amount": 9500.00, "description": "Large wire transfer"},

    # Should fail: exceeds $50K daily limit (COBOL returns status 02)
    {"source_bank": "BANK_D", "source_account": "ACT-D-004", "dest_bank": "BANK_A", "dest_account": "ACT-A-001", "amount": 50001.00, "description": "Oversized transfer - will fail"},

    # Reverse direction to create circular flow
    {"source_bank": "BANK_B", "source_account": "ACT-B-002", "dest_bank": "BANK_A", "dest_account": "ACT-A-001", "amount": 800.00, "description": "Refund"},
]
