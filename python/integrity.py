"""
IntegrityChain -- SHA-256 hash chain with HMAC signature verification.

This module implements a cryptographic audit trail for every transaction processed
by the banking system. It is the core of the "observability layer" that wraps
unmodified COBOL programs.

How it works:
    Each transaction is hashed (SHA-256) together with the hash of the PREVIOUS
    transaction. This creates a chain where modifying any single entry invalidates
    every entry that comes after it. An attacker cannot edit a historical record
    without breaking the chain from that point forward.

    Additionally, each hash is signed with an HMAC (keyed-hash message
    authentication code) using a per-node secret key. This means even if someone
    recomputes the SHA-256 chain after tampering, the HMAC signatures will not
    match unless they also possess the secret key.

Why this matters for COBOL integration:
    COBOL programs read and write flat files (ACCOUNTS.DAT, TRANSACT.DAT).
    Anyone with file system access can edit those files directly. The integrity
    chain lives in SQLite, separate from the COBOL data files, and provides
    an independent cryptographic witness of what the COBOL programs actually did.

Chain structure:
    [GENESIS] -> entry_0 -> entry_1 -> entry_2 -> ...
    Each entry stores: prev_hash (link), tx_hash (content hash), signature (HMAC)

Detection guarantees:
    - Modified transaction: hash changes, chain breaks at that entry
    - Deleted transaction: next entry's prev_hash won't match, chain breaks
    - Inserted transaction: same as modified -- shifts all subsequent hashes
    - Recomputed chain without key: HMAC signatures fail verification

Performance:
    Chain verification is O(n) -- walks every entry once. The verify_chain()
    method returns timing data to prove sub-100ms verification for typical
    transaction volumes (< 10,000 entries).
"""
import hashlib
import hmac
import sqlite3
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# ── Genesis Constant ──────────────────────────────────────────
# The genesis hash is the "previous hash" for the very first entry in any
# chain. It anchors the chain and has no cryptographic significance -- it
# simply signals "this is the beginning." Every node's chain starts here.
GENESIS_HASH = "GENESIS"

@dataclass
class ChainedTransaction:
    """A single entry in the integrity chain.

    Each entry is a self-contained proof of a transaction: the content hash
    links it to the previous entry (chain integrity), and the HMAC signature
    proves it was created by an authorized node (authenticity).
    """
    chain_index: int
    tx_id: str
    account_id: str
    tx_type: str
    amount: float
    timestamp: str
    description: str
    status: str
    tx_hash: str
    prev_hash: str
    signature: str


class IntegrityChain:
    """SHA-256 hash chain stored in SQLite, providing tamper-evident logging.

    One IntegrityChain instance exists per banking node. The chain is append-only:
    entries are never updated or deleted during normal operation. Verification
    walks the chain from genesis to the latest entry, checking both hash linkage
    and HMAC signatures.
    """
    def __init__(self, db_connection: sqlite3.Connection, secret_key: str):
        self.db = db_connection
        # The secret key is per-node, stored in .server_key file.
        # It is used for HMAC signing -- without this key, an attacker
        # cannot forge valid signatures even if they recompute hashes.
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key
        self._ensure_table()

    def _ensure_table(self):
        """Create chain_entries table if it doesn't exist"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS chain_entries (
                chain_index INTEGER PRIMARY KEY,
                tx_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                tx_type TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                tx_hash TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                signature TEXT NOT NULL
            )
        """)
        self.db.commit()

    def get_latest_hash(self) -> str:
        """Get the hash of the most recent entry (or GENESIS_HASH if empty)"""
        cursor = self.db.execute(
            "SELECT tx_hash FROM chain_entries ORDER BY chain_index DESC LIMIT 1"
        )
        result = cursor.fetchone()
        return result[0] if result else GENESIS_HASH

    def append(self, tx_id: str, account_id: str, tx_type: str, amount: float,
               timestamp: str, description: str, status: str) -> ChainedTransaction:
        """Append a transaction to the chain.

        This is the only way to add entries. The method:
        1. Retrieves the latest hash (or GENESIS for empty chains)
        2. Constructs a content string from all transaction fields + prev_hash
        3. Computes SHA-256 of the content (the "chain link")
        4. Computes HMAC-SHA256 of the hash using the node's secret key
        5. Stores everything in SQLite as an atomic row insert
        """

        # ── Step 1: Chain Linkage ─────────────────────────────────────
        # The previous hash ties this entry to the one before it.
        # For the first entry, prev_hash will be "GENESIS".
        prev_hash = self.get_latest_hash()

        # ── Step 2: Content Hashing ───────────────────────────────────
        # All transaction fields are concatenated with pipe delimiters.
        # Including prev_hash in the content means the hash of THIS entry
        # depends on the hash of the PREVIOUS entry -- creating the chain.
        contents = f"{tx_id}|{account_id}|{tx_type}|{amount}|{timestamp}|{description}|{status}|{prev_hash}"

        # ── Step 3: SHA-256 Hash ──────────────────────────────────────
        # This is the "fingerprint" of the transaction + its position in
        # the chain. Change any field (or any prior entry), and this hash
        # will be different.
        tx_hash = hashlib.sha256(contents.encode()).hexdigest()

        # ── Step 4: HMAC Signature ────────────────────────────────────
        # HMAC proves this entry was created by someone who knows the
        # secret key. Even if an attacker recomputes the SHA-256 chain
        # after tampering, they cannot produce valid HMAC signatures.
        signature = hmac.new(self.secret_key, tx_hash.encode(), hashlib.sha256).hexdigest()

        # ── Step 5: Persist to SQLite ─────────────────────────────────
        # Get next chain index
        cursor = self.db.execute("SELECT MAX(chain_index) FROM chain_entries")
        max_index = cursor.fetchone()[0]
        chain_index = 0 if max_index is None else max_index + 1

        # Insert into database
        self.db.execute("""
            INSERT INTO chain_entries
            (chain_index, tx_id, account_id, tx_type, amount, timestamp, description, status, tx_hash, prev_hash, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (chain_index, tx_id, account_id, tx_type, amount, timestamp, description, status, tx_hash, prev_hash, signature))
        self.db.commit()

        return ChainedTransaction(
            chain_index=chain_index,
            tx_id=tx_id,
            account_id=account_id,
            tx_type=tx_type,
            amount=amount,
            timestamp=timestamp,
            description=description,
            status=status,
            tx_hash=tx_hash,
            prev_hash=prev_hash,
            signature=signature
        )

    def verify_chain(self) -> Dict[str, Any]:
        """Verify integrity of the entire chain.

        Walks every entry from index 0 to the end, performing two checks:

        Check 1 -- Chain linkage: Each entry's stored prev_hash must match
        the tx_hash of the preceding entry. A mismatch means either an entry
        was modified, deleted, or inserted out of order.

        Check 2 -- HMAC signature: Each entry's signature must match the
        HMAC computed from tx_hash using the node's secret key. A mismatch
        means either the hash was tampered with or the entry was created
        by someone without the key.

        Returns a dict with:
            valid: bool -- True if entire chain passes both checks
            entries_checked: int -- how many entries were verified
            time_ms: float -- wall-clock verification time
            first_break: int or None -- chain_index of first failure
            break_type: str or None -- "linkage_break" or "signature_invalid"
        """
        start_time = datetime.now()

        cursor = self.db.execute(
            "SELECT chain_index, tx_id, account_id, tx_type, amount, "
            "timestamp, description, status, tx_hash, prev_hash, signature "
            "FROM chain_entries ORDER BY chain_index"
        )
        entries = cursor.fetchall()

        if not entries:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "valid": True,
                "entries_checked": 0,
                "time_ms": elapsed_ms,
                "first_break": None,
                "break_type": None,
                "details": "Empty chain (valid initial state)"
            }

        # ── O(n) Chain Walk ───────────────────────────────────────────
        # Start from GENESIS and verify each link in sequence.
        # Three checks per entry: linkage, content hash, HMAC signature.
        # Early exit on first failure -- no need to check the rest.
        prev_hash = GENESIS_HASH
        for idx, (chain_idx, tx_id, account_id, tx_type, amount,
                  timestamp, description, status, tx_hash,
                  stored_prev_hash, signature) in enumerate(entries):
            # Check 1: Chain linkage -- prev_hash must match previous entry's tx_hash
            if stored_prev_hash != prev_hash:
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "valid": False,
                    "entries_checked": idx,
                    "time_ms": elapsed_ms,
                    "first_break": chain_idx,
                    "break_type": "linkage_break",
                    "details": f"Entry {chain_idx} prev_hash mismatch: expected {prev_hash}, got {stored_prev_hash}"
                }

            # Check 2: Content hash -- recompute SHA-256 from stored fields
            # and verify it matches the stored tx_hash. This catches edits
            # to transaction fields (amount, description, etc.) even if
            # the attacker preserved the chain linkage.
            contents = f"{tx_id}|{account_id}|{tx_type}|{amount}|{timestamp}|{description}|{status}|{stored_prev_hash}"
            expected_hash = hashlib.sha256(contents.encode()).hexdigest()
            if tx_hash != expected_hash:
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "valid": False,
                    "entries_checked": idx + 1,
                    "time_ms": elapsed_ms,
                    "first_break": chain_idx,
                    "break_type": "content_hash_mismatch",
                    "details": f"Entry {chain_idx} content hash mismatch: stored hash does not match recomputed hash"
                }

            # Check 3: HMAC Signature validity
            expected_sig = hmac.new(self.secret_key, tx_hash.encode(), hashlib.sha256).hexdigest()
            if signature != expected_sig:
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "valid": False,
                    "entries_checked": idx + 1,
                    "time_ms": elapsed_ms,
                    "first_break": chain_idx,
                    "break_type": "signature_invalid",
                    "details": f"Entry {chain_idx} signature verification failed"
                }

            prev_hash = tx_hash

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        return {
            "valid": True,
            "entries_checked": len(entries),
            "time_ms": elapsed_ms,
            "first_break": None,
            "break_type": None,
            "details": f"All {len(entries)} entries verified. Chain intact in {elapsed_ms:.1f}ms."
        }

    def get_chain_for_display(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get chain entries formatted for display.

        Returns truncated hashes (first 8 hex chars) for human readability.
        Full hashes are 64 characters -- too long for tabular display.
        """
        cursor = self.db.execute("""
            SELECT chain_index, tx_id, tx_hash, prev_hash, signature
            FROM chain_entries
            ORDER BY chain_index
            LIMIT ? OFFSET ?
        """, (limit, offset))

        return [
            {
                "chain_index": row[0],
                "tx_id": row[1],
                "hash": row[2][:8],  # Short hash for display
                "prev_hash": row[3][:8],
                "signature": row[4][:8]
            }
            for row in cursor.fetchall()
        ]
