"""
models -- Pydantic request/response schemas for the REST API.

Every HTTP endpoint in the API layer uses typed Pydantic models for both
request validation and response serialization. This module is the single
source of truth for the API contract.

Why Pydantic (not plain dicts):
    Pydantic provides automatic JSON Schema generation (powering the /docs
    page), request validation with clear error messages, and type safety.
    Field constraints (pattern, gt, max_length) mirror the COBOL record
    format restrictions — a PIC X(40) field maps to max_length=40, a
    PIC S9(10)V99 field maps to a float with implicit two-decimal precision.

Three model groups:
    Banking models   — Account, Transaction, Transfer, Chain, Settlement, Node
    Codegen models   — Parse, Generate, Edit, Validate request/response pairs
    Chat/LLM models  — Chat, ToolCall, Provider status/switch

Field pattern design:
    Account ID patterns (^ACT-[A-E]-\\d{3}$) enforce the same format as the
    COBOL ACCT-ID PIC X(10) field. Bank node patterns (^BANK_[A-E]$) match
    the 6-node architecture. These regex constraints catch invalid input at
    the HTTP boundary before it reaches the bridge layer.

Dependencies:
    pydantic
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ── Banking Models ─────────────────────────────────────────────────
# Request/response schemas for account CRUD, transactions, chain ops,
# and inter-bank settlement. Field constraints mirror COBOL record formats.

class AccountResponse(BaseModel):
    """Single account record returned by GET /api/nodes/{node}/accounts/{id}."""
    account_id: str                # ACCT-ID PIC X(10)
    name: str                      # ACCT-NAME PIC X(30)
    account_type: str              # ACCT-TYPE PIC X (C=checking, S=savings, N=nostro)
    balance: float                 # ACCT-BALANCE PIC S9(10)V99, implied decimal
    status: str                    # ACCT-STATUS PIC X (A=active, F=frozen, C=closed)
    open_date: str                 # ACCT-OPEN-DATE PIC X(8), YYYYMMDD
    last_activity: str             # ACCT-LAST-ACTIVITY PIC X(8), YYYYMMDD


class TransactionRequest(BaseModel):
    """Request body for POST /api/nodes/{node}/transactions."""
    account_id: str = Field(..., pattern=r"^ACT-[A-E]-\d{3}$|^NST-BANK-[A-E]$")  # Matches ACCT-ID PIC X(10) format
    tx_type: str = Field(..., pattern=r"^[DWTIF]$", description="D=deposit, W=withdraw, T=transfer, I=interest, F=fee")  # TRANS-TYPE PIC X
    amount: float = Field(..., gt=0)                            # Must be positive — COBOL checks this too
    description: str = Field(default="", max_length=40)         # TRANS-DESC PIC X(40)
    target_id: Optional[str] = Field(default=None, pattern=r"^ACT-[A-E]-\d{3}$|^NST-BANK-[A-E]$")  # Required for T (transfer)


class TransactionResponse(BaseModel):
    """Response from POST /api/nodes/{node}/transactions."""
    status: str                    # COBOL status code: 00=success, 01=NSF, etc.
    tx_id: Optional[str] = None    # TRANS-ID PIC X(12), e.g., TRX-A-000042
    new_balance: Optional[float] = None  # Updated balance after transaction
    message: str                   # Human-readable status description


class TransferRequest(BaseModel):
    """Request body for POST /api/settlement/transfer (inter-bank)."""
    source_bank: str = Field(..., pattern=r"^BANK_[A-E]$")     # Source node
    source_account: str = Field(..., pattern=r"^ACT-[A-E]-\d{3}$")  # Sender account
    dest_bank: str = Field(..., pattern=r"^BANK_[A-E]$")       # Destination node
    dest_account: str = Field(..., pattern=r"^ACT-[A-E]-\d{3}$")    # Receiver account
    amount: float = Field(..., gt=0)                            # Transfer amount
    description: str = Field(default="")                        # Optional narrative


class TransferResponse(BaseModel):
    """Response from POST /api/settlement/transfer."""
    status: str                    # SUCCESS, PARTIAL_FAILURE, or FAILED
    settlement_ref: str            # STL-YYYYMMDD-NNNNNN cross-node reference
    source_trx_id: str             # Transaction ID at source bank
    dest_trx_id: str               # Transaction ID at destination bank
    amount: float                  # Confirmed transfer amount
    steps_completed: int           # 0-3 legs completed (of the 3-leg settlement)
    error: str                     # Empty on success, describes failure otherwise


class ChainEntry(BaseModel):
    """Single integrity chain entry returned by GET /api/nodes/{node}/chain."""
    chain_index: int               # Sequential position in the chain (0-based)
    tx_id: str                     # TRANS-ID PIC X(12)
    account_id: str                # ACCT-ID PIC X(10)
    tx_type: str                   # D/W/T/I/F
    amount: float                  # Transaction amount
    timestamp: str                 # ISO 8601 timestamp
    tx_hash: str                   # SHA-256 hex digest (64 chars)
    prev_hash: str                 # Previous entry's hash or "GENESIS"


class ChainVerifyResponse(BaseModel):
    """Response from POST /api/nodes/{node}/chain/verify."""
    valid: bool                    # True if entire chain is intact
    entries_checked: int           # Number of entries verified
    time_ms: float                 # Verification time in milliseconds
    first_break: Optional[int] = None   # Chain index of first break (if any)
    break_type: Optional[str] = None    # "linkage" or "signature"


class VerificationResponse(BaseModel):
    """Response from POST /api/settlement/verify (cross-node verification)."""
    timestamp: str                           # When verification ran
    chain_integrity: Dict[str, bool]         # Per-node chain validity
    chain_lengths: Dict[str, int]            # Per-node chain length
    all_chains_intact: bool                  # True if all 6 chains valid
    all_settlements_matched: bool            # True if all settlement refs match
    settlements_checked: int                 # Number of settlement refs checked
    settlements_matched: int                 # Refs that matched across nodes
    settlements_mismatched: int              # Refs with discrepancies
    anomalies: List[str]                     # Human-readable anomaly descriptions
    verification_time_ms: float              # Total verification time


class NodeInfo(BaseModel):
    """Node summary returned by GET /api/nodes."""
    node: str                      # Node name (BANK_A, CLEARING, etc.)
    account_count: int             # Number of accounts in this node
    chain_length: int              # Number of integrity chain entries
    chain_valid: bool              # Whether chain passes verification


# ── Codegen Models ─────────────────────────────────────────────────
# Request/response schemas for the COBOL code generation pipeline.
# These map to cobol_codegen module operations: parse, generate, edit, validate.

class CodegenParseRequest(BaseModel):
    """Request body for POST /api/codegen/parse."""
    file_path: Optional[str] = None     # Path to .cob/.cpy file on disk
    source_text: Optional[str] = None   # Or inline COBOL source text


class CodegenParseResponse(BaseModel):
    """AST summary returned by POST /api/codegen/parse."""
    program_id: str                # PROGRAM-ID from IDENTIFICATION DIVISION
    author: str                    # AUTHOR paragraph (if present)
    paragraphs: List[str]          # Paragraph names from PROCEDURE DIVISION
    files: List[str]               # FILE-CONTROL logical file names
    copybooks: List[str]           # COPY statement references
    working_storage_fields: int    # Count of WORKING-STORAGE data items


class CodegenGenerateRequest(BaseModel):
    """Request body for POST /api/codegen/generate."""
    template: str = Field(..., description="Template type: crud, report, batch, copybook")
    name: str                      # Program name or copybook name
    params: Dict[str, Any] = Field(default_factory=dict)  # Template-specific parameters


class CodegenGenerateResponse(BaseModel):
    """Generated COBOL source returned by POST /api/codegen/generate."""
    source: str                    # Complete COBOL source text
    program_id: str                # PROGRAM-ID of generated program
    line_count: int                # Number of lines generated


class CodegenEditRequest(BaseModel):
    """Request body for POST /api/codegen/edit."""
    source_text: str               # COBOL source to edit
    operation: str = Field(..., description="Operation: add_field, remove_field, add_paragraph, rename_paragraph, add_operation, add_88_condition, add_copybook_ref, update_pic")
    params: Dict[str, Any] = Field(default_factory=dict)  # Operation-specific params


class CodegenEditResponse(BaseModel):
    """Edited COBOL source returned by POST /api/codegen/edit."""
    source: str                    # Modified COBOL source text
    message: str                   # Description of what was changed
    line_count: int                # Number of lines in result


class CodegenValidateRequest(BaseModel):
    """Request body for POST /api/codegen/validate."""
    file_path: Optional[str] = None     # Path to .cob/.cpy file on disk
    source_text: Optional[str] = None   # Or inline COBOL source text


class ValidationIssueResponse(BaseModel):
    """Single validation issue within a CodegenValidateResponse."""
    severity: str                  # "ERROR" or "WARNING"
    message: str                   # Human-readable issue description
    location: Optional[str] = None  # Source location (if identifiable)


class CodegenValidateResponse(BaseModel):
    """Validation results returned by POST /api/codegen/validate."""
    valid: bool                    # True if zero errors (warnings allowed)
    issues: List[ValidationIssueResponse]  # All issues found
    error_count: int               # Number of ERROR-severity issues
    warning_count: int             # Number of WARNING-severity issues


# ── Chat/LLM Models ───────────────────────────────────────────────
# Request/response schemas for the LLM chat endpoint and provider management.
# These wrap the ConversationManager's dict-based results as typed models.

class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""
    message: str = Field(..., min_length=1)         # User message (cannot be empty)
    session_id: Optional[str] = None                # Reuse existing session, or None for new


class ToolCallInfo(BaseModel):
    """Record of a single tool call resolved during chat."""
    tool_name: str                 # Tool that was called (e.g., "list_accounts")
    params: Dict[str, Any]         # Arguments passed to the tool
    result: Dict[str, Any]         # Tool execution result
    permitted: bool                # Whether RBAC allowed the call


class ChatResponse(BaseModel):
    """Response from POST /api/chat."""
    response: str                  # LLM's final text response
    session_id: str                # Session ID (for continuing the conversation)
    tool_calls: List[ToolCallInfo] = Field(default_factory=list)  # Tools invoked during this turn
    provider: str                  # Provider used (ollama or anthropic)
    model: str                     # Model used (llama3.1, claude-sonnet-4-20250514, etc.)


class ProviderStatus(BaseModel):
    """Response from GET /api/provider/status."""
    provider: str                  # Current provider name
    model: str                     # Current model name
    security_level: str            # LOCAL (Ollama) or CLOUD (Anthropic)
    available: bool                # Whether the provider is reachable
    error: Optional[str] = None    # Error message if unavailable


class ProviderSwitchRequest(BaseModel):
    """Request body for POST /api/provider/switch."""
    provider: str = Field(..., pattern=r"^(ollama|anthropic)$")  # Target provider
    model: Optional[str] = None    # Optional model override


# ── Health Models ──────────────────────────────────────────────────
# Response schema for the unauthenticated health check endpoint.

class HealthResponse(BaseModel):
    """Response from GET /api/health."""
    status: str                    # "healthy" (all 6 nodes) or "degraded"
    nodes_available: int           # Count of nodes with data directories
    ollama_available: bool         # Whether Ollama API responds
    anthropic_configured: bool     # Whether ANTHROPIC_API_KEY is set
    db_status: str                 # "ok" or "no_data"
    version: str                   # API version (currently "3.0.0")
