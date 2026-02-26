"""
tools -- LLM tool definitions in Anthropic-compatible JSON Schema format.

This module defines the 12 tools that an LLM can invoke during a conversation.
Each tool maps to an existing bridge, settlement, or codegen method — no new
business logic is introduced here. The definitions are plain dicts (not classes)
because both Ollama and Anthropic expect JSON-serializable tool schemas.

Why plain dicts (not Pydantic or dataclasses):
    The Anthropic API expects tool definitions as JSON objects with specific
    keys: name, description, input_schema. Ollama expects a similar format
    wrapped in a "function" key. Plain dicts are the lowest-common-denominator
    format that both providers can consume with minimal transformation.

The `required_permission` field:
    Each tool includes a `required_permission` key that maps to the RBAC
    permission matrix in auth.py. This field is INTERNAL — it's used by the
    ToolExecutor to gate access before dispatch, but it's stripped from the
    schema before sending to the LLM (the LLM doesn't need to know about
    permissions, it just calls tools and gets results or denial messages).

Tool groups:
    Banking tools (8): list_accounts, get_account, process_transaction,
        verify_chain, view_chain, transfer, verify_all_nodes, run_reconciliation
    Codegen tools (4): parse_cobol, generate_cobol, edit_cobol, validate_cobol

Dependencies:
    python.auth (Role, PERMISSIONS)
"""

from typing import List, Dict, Any
from python.auth import Role, PERMISSIONS


# ── Tool Definitions ──────────────────────────────────────────────
# Each dict follows the Anthropic tool schema: name, description, input_schema.
# The `required_permission` field is an internal gate — stripped before sending
# to the LLM provider.

TOOLS: List[Dict[str, Any]] = [
    # ── Banking Tools ─────────────────────────────────────────────
    {
        "name": "list_accounts",
        "description": "List all accounts for a banking node. Returns account IDs, names, balances, and statuses.",
        "required_permission": "accounts.read",          # CLI: list-accounts
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Banking node name",
                    "enum": ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"],
                },
            },
            "required": ["node"],
        },
    },
    {
        "name": "get_account",
        "description": "Get details for a specific account by ID.",
        "required_permission": "accounts.read",          # CLI: get-account
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "enum": ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"],
                },
                "account_id": {
                    "type": "string",
                    "description": "Account ID (e.g., ACT-A-001)",
                },
            },
            "required": ["node", "account_id"],
        },
    },
    {
        "name": "process_transaction",
        "description": "Process a financial transaction: deposit (D), withdraw (W), transfer (T), interest (I), or fee (F).",
        "required_permission": "transactions.process",   # CLI: transact
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "enum": ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"],
                },
                "account_id": {"type": "string"},
                "tx_type": {
                    "type": "string",
                    "enum": ["D", "W", "T", "I", "F"],
                    "description": "D=deposit, W=withdraw, T=transfer, I=interest, F=fee",
                },
                "amount": {"type": "number", "minimum": 0.01},
                "description": {"type": "string", "default": ""},
                "target_id": {"type": "string", "description": "Required for transfers (T)"},
            },
            "required": ["node", "account_id", "tx_type", "amount"],
        },
    },
    {
        "name": "verify_chain",
        "description": "Verify the SHA-256 integrity chain for a specific node. Returns valid/invalid status and break details.",
        "required_permission": "chain.verify",           # CLI: verify
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "enum": ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"],
                },
            },
            "required": ["node"],
        },
    },
    {
        "name": "view_chain",
        "description": "View recent chain entries for a node. Shows transaction IDs, amounts, and hashes.",
        "required_permission": "chain.view",             # CLI: chain
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "enum": ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"],
                },
                "limit": {"type": "integer", "default": 20, "maximum": 100},
            },
            "required": ["node"],
        },
    },
    {
        "name": "transfer",
        "description": "Execute an inter-bank settlement transfer through the clearing house (3-leg settlement).",
        "required_permission": "transactions.process",   # CLI: settle
        "input_schema": {
            "type": "object",
            "properties": {
                "source_bank": {"type": "string", "enum": ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"]},
                "source_account": {"type": "string"},
                "dest_bank": {"type": "string", "enum": ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"]},
                "dest_account": {"type": "string"},
                "amount": {"type": "number", "minimum": 0.01},
                "description": {"type": "string", "default": ""},
            },
            "required": ["source_bank", "source_account", "dest_bank", "dest_account", "amount"],
        },
    },
    {
        "name": "verify_all_nodes",
        "description": "Run cross-node verification: checks all chains, balance drift, and settlement matching across all 6 nodes.",
        "required_permission": "chain.verify",           # CLI: verify --all
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "run_reconciliation",
        "description": "Run transaction-to-balance reconciliation for a node. Compares computed balances against stored balances.",
        "required_permission": "transactions.read",      # CLI: reconcile
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "enum": ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"],
                },
            },
            "required": ["node"],
        },
    },
    # ── Codegen Tools ─────────────────────────────────────────────
    {
        "name": "parse_cobol",
        "description": "Parse COBOL source text into an AST summary. Returns program ID, paragraphs, files, and field counts.",
        "required_permission": "cobol.read",             # Read-only analysis
        "input_schema": {
            "type": "object",
            "properties": {
                "source_text": {"type": "string", "description": "COBOL source code to parse"},
            },
            "required": ["source_text"],
        },
    },
    {
        "name": "generate_cobol",
        "description": "Generate COBOL source from a template (crud, report, batch, copybook).",
        "required_permission": "cobol.read",             # Generation is read-like (no side effects)
        "input_schema": {
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                    "enum": ["crud", "report", "batch", "copybook"],
                },
                "name": {"type": "string", "description": "Program or copybook name"},
                "params": {"type": "object", "description": "Template parameters"},
            },
            "required": ["template", "name"],
        },
    },
    {
        "name": "edit_cobol",
        "description": "Edit COBOL source via AST operations (add_field, remove_field, add_paragraph, etc.).",
        "required_permission": "cobol.read",             # In-memory edit, no file writes
        "input_schema": {
            "type": "object",
            "properties": {
                "source_text": {"type": "string"},
                "operation": {
                    "type": "string",
                    "enum": ["add_field", "remove_field", "add_paragraph", "rename_paragraph",
                             "add_operation", "add_88_condition", "add_copybook_ref", "update_pic"],
                },
                "params": {"type": "object"},
            },
            "required": ["source_text", "operation", "params"],
        },
    },
    {
        "name": "validate_cobol",
        "description": "Validate COBOL source against project conventions. Returns errors and warnings.",
        "required_permission": "cobol.read",             # Read-only validation
        "input_schema": {
            "type": "object",
            "properties": {
                "source_text": {"type": "string"},
            },
            "required": ["source_text"],
        },
    },
]


# ── Role-Based Filtering ─────────────────────────────────────────
# Returns only the tools a given role is permitted to use.

def get_tools_for_role(role: Role) -> List[Dict[str, Any]]:
    """Filter tools to only those the given role has permission to use.

    1. Look up the role's permission set from the PERMISSIONS matrix
    2. For each tool, check if its required_permission is in that set
    3. Strip the internal required_permission field from returned dicts
       (the LLM doesn't need to see RBAC internals)

    Returns:
        List of Anthropic-compatible tool dicts (name, description, input_schema).
    """
    role_perms = PERMISSIONS.get(role, set())
    result = []
    for tool in TOOLS:
        if tool["required_permission"] in role_perms:
            # Return Anthropic-compatible schema without internal gate field
            result.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            })
    return result


def get_tool_definition(name: str) -> Dict[str, Any]:
    """Get a tool definition by name, including internal fields.

    Returns None if no tool with that name exists. Used by ToolExecutor
    to look up the required_permission before dispatch.
    """
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None
