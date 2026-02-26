"""
AuditLog -- SQLite audit log for all LLM tool invocations.

This module records every tool call made through the ToolExecutor, whether
permitted or denied. It is intentionally separate from the integrity chain
(python/integrity.py) because they serve different purposes:

    Integrity chain: Financial transaction data. Cryptographically linked.
        Lives in each node's SQLite database. Used for tamper detection.

    Audit log: LLM interaction data. Simple append-only table. Lives in a
        separate database file. Used for observability and debugging.

Schema design:
    The tool_audit table stores: timestamp, user_id, role, provider (which
    LLM made the call), tool_name, params (JSON), result (JSON, nullable),
    permitted (integer 0/1), and error (text). The `permitted` column uses
    integer 0/1 because SQLite has no native boolean type — this matches
    SQLite conventions.

Retention:
    No automatic retention policy. For a demo system, the audit log grows
    slowly (hundreds of entries per session). Production would add rotation
    or archival.

Dependencies:
    sqlite3, json (standard library only)
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


class AuditLog:
    """Logs all LLM tool invocations to a SQLite database.

    One instance per application process. The database file defaults to
    llm_audit.db in the current directory. Test fixtures provide a temp
    path to isolate test data.
    """

    def __init__(self, db_path: str = "llm_audit.db"):
        """Initialize the audit log.

        :param db_path: Path to the SQLite database file (created if missing)
        """
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row    # Enable dict-like row access
        self._init_table()

    # ── Schema ────────────────────────────────────────────────────
    # Single table, auto-increment ID, append-only.

    def _init_table(self):
        """Create the tool_audit table if it doesn't exist."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS tool_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                provider TEXT,
                tool_name TEXT NOT NULL,
                params TEXT NOT NULL,
                result TEXT,
                permitted INTEGER NOT NULL,
                error TEXT
            )
        """)
        self.db.commit()

    # ── Write ─────────────────────────────────────────────────────
    # Record a single tool invocation (permitted or denied).

    def record(
        self,
        user_id: str,
        role: str,
        tool_name: str,
        params: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        permitted: bool = True,
        provider: str = "",
        error: str = "",
    ):
        """Record a tool invocation (permitted or denied).

        The `permitted` bool is stored as integer 0/1 because SQLite has no
        native boolean type. The `result` is JSON-serialized and nullable
        (None when the call was denied or errored before producing a result).
        """
        self.db.execute(
            """INSERT INTO tool_audit (timestamp, user_id, role, provider, tool_name, params, result, permitted, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),  # UTC timestamp
                user_id,
                role,
                provider,
                tool_name,
                json.dumps(params),                      # Serialize params as JSON string
                json.dumps(result) if result else None,   # Nullable — None for denials
                1 if permitted else 0,                    # SQLite bool: 1=True, 0=False
                error,
            ),
        )
        self.db.commit()

    # ── Read ──────────────────────────────────────────────────────
    # Query recent audit entries for display or testing.

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get the most recent audit entries, newest first."""
        rows = self.db.execute(
            "SELECT * FROM tool_audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "user_id": r["user_id"],
                "role": r["role"],
                "provider": r["provider"],
                "tool_name": r["tool_name"],
                "params": json.loads(r["params"]),           # Deserialize JSON
                "result": json.loads(r["result"]) if r["result"] else None,
                "permitted": bool(r["permitted"]),            # Convert 0/1 back to bool
                "error": r["error"],
            }
            for r in rows
        ]

    def close(self):
        """Close the database connection."""
        self.db.close()
