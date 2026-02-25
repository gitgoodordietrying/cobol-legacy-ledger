"""
CLI commands for cobol-legacy-ledger.

This module provides the command-line interface using the Click framework.
Each CLI command maps to one or more COBOLBridge operations, providing a
human-friendly way to interact with the banking system.

Architecture:
    CLI commands are thin wrappers -- they parse arguments, instantiate the
    appropriate bridge/coordinator/verifier, call its methods, and format
    the output. No business logic lives here.

Command mapping:
    init-db        -> COBOLBridge.seed_demo_data() for one node
    seed-all       -> COBOLBridge.seed_demo_data() for all 6 nodes
    list-accounts  -> COBOLBridge.list_accounts()
    get-account    -> COBOLBridge.get_account()
    transact       -> COBOLBridge.process_transaction()
    verify-chain   -> IntegrityChain.verify_chain()
    transfer       -> SettlementCoordinator.execute_transfer()
    settle         -> SettlementCoordinator.execute_batch_settlement()
    verify         -> CrossNodeVerifier.verify_all()
    tamper-demo    -> cross_verify.tamper_balance()
    simulate       -> SimulationEngine.run()
    interest       -> COBOLBridge.run_interest_batch()
    fees           -> COBOLBridge.run_fee_batch()
    reconcile      -> COBOLBridge.run_reconciliation()

Entry point: python -m bridge cli <command> [args]
"""

import click
import sys
from pathlib import Path
from .bridge import COBOLBridge
from .auth import Role, get_auth_context
from .settlement import SettlementCoordinator, DEMO_SETTLEMENT_BATCH
from .cross_verify import CrossNodeVerifier, tamper_balance
from .simulator import SimulationEngine


@click.group()
def cli():
    """cobol-legacy-ledger command-line interface."""
    pass


# ── Node Initialization ──────────────────────────────────────────
# These commands set up node databases and seed demo data.

@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier (BANK_A, BANK_B, ..., CLEARING)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def init_db(node: str, data_dir: str):
    """Initialize database and integrity chain for a node."""
    click.echo(f"Initializing {node} database...")

    bridge = COBOLBridge(node=node, data_dir=data_dir)
    bridge.seed_demo_data()
    bridge.close()

    click.echo(f"✓ {node} initialized at {data_dir}/{node.lower()}/")


@cli.command()
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def seed_all(data_dir: str):
    """Seed all 6 nodes with demo accounts."""
    nodes = ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']

    click.echo("Seeding all nodes...")
    for node in nodes:
        try:
            bridge = COBOLBridge(node=node, data_dir=data_dir)
            bridge.seed_demo_data()
            bridge.close()
            click.echo(f"  ✓ {node}")
        except Exception as e:
            click.echo(f"  ✗ {node}: {e}", err=True)

    click.echo(f"✓ All {len(nodes)} nodes seeded")


# ── Account Queries ───────────────────────────────────────────────
# Read-only commands that inspect account data on a single node.

@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def list_accounts(node: str, data_dir: str):
    """List all accounts on a node."""
    bridge = COBOLBridge(node=node, data_dir=data_dir)
    accounts = bridge.list_accounts()
    bridge.close()

    if not accounts:
        click.echo(f"No accounts on {node}")
        return

    click.echo(f"\n{node} Accounts ({len(accounts)}):")
    click.echo(f"{'ID':<12} {'Name':<30} {'Type':<4} {'Balance':>12} {'Status':<6}")
    click.echo("-" * 70)
    for acct in accounts:
        click.echo(
            f"{acct['id']:<12} {acct['name']:<30} {acct['type']:<4} "
            f"${acct['balance']:>11.2f} {acct['status']:<6}"
        )


@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier')
@click.option('--account-id', prompt='Account ID', help='Account to query')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def get_account(node: str, account_id: str, data_dir: str):
    """Get details of a single account."""
    bridge = COBOLBridge(node=node, data_dir=data_dir)
    account = bridge.get_account(account_id)
    bridge.close()

    if not account:
        click.echo(f"Account {account_id} not found on {node}", err=True)
        sys.exit(1)

    click.echo(f"\n{node} Account: {account_id}")
    click.echo(f"  Name:            {account['name']}")
    click.echo(f"  Type:            {account['type']}")
    click.echo(f"  Balance:         ${account['balance']:.2f}")
    click.echo(f"  Status:          {account['status']}")
    click.echo(f"  Opened:          {account.get('open_date', 'N/A')}")
    click.echo(f"  Last Activity:   {account.get('last_activity', 'N/A')}")


# ── Single-Node Transactions ─────────────────────────────────────
# Process transactions on a single node (deposit, withdraw, transfer).

@cli.command()
@click.option('--node', default='BANK_A', help='Source node')
@click.option('--account-id', prompt='Account ID', help='Source account')
@click.option('--tx-type', type=click.Choice(['D', 'W', 'T'], case_sensitive=False),
              prompt='Type (D=deposit, W=withdraw, T=transfer)', help='Transaction type')
@click.option('--amount', prompt='Amount', type=float, help='Amount')
@click.option('--description', prompt='Description', default='CLI transaction', help='Description')
@click.option('--target-id', default=None, help='Target account (for transfers)')
@click.option('--user', default='admin', help='User identity for RBAC (default: admin)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def transact(node: str, account_id: str, tx_type: str, amount: float, description: str,
             target_id: str, user: str, data_dir: str):
    """Process a transaction."""
    auth = get_auth_context(user)
    try:
        auth.require_permission("transactions.process")
    except PermissionError as e:
        click.echo(f"Access denied: {e}", err=True)
        sys.exit(1)

    bridge = COBOLBridge(node=node, data_dir=data_dir)

    result = bridge.process_transaction(account_id, tx_type.upper(), amount, description, target_id)
    bridge.close()

    if result['status'] == '00':
        click.echo(f"✓ Transaction {result['tx_id']} processed")
        click.echo(f"  New balance: ${result.get('new_balance', 'N/A'):.2f}")
    else:
        status_msg = {
            '01': 'Insufficient funds',
            '02': 'Limit exceeded',
            '03': 'Invalid account',
            '04': 'Account frozen',
        }.get(result['status'], f"Error {result['status']}")
        click.echo(f"✗ {status_msg}: {result['message']}", err=True)
        sys.exit(1)


# ── Validation ──────────────────────────────────────────────────
# Pre-flight check: validate a transaction without executing it.

@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier')
@click.option('--account', required=True, help='Account to validate (e.g., ACT-A-001)')
@click.option('--amount', type=float, required=True, help='Amount to validate')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def validate(node: str, account: str, amount: float, data_dir: str):
    """Validate a transaction without executing it.

    Checks account existence, frozen status, balance, and daily limits.
    Returns pass/fail with reason code.

    Example: legacyledger validate --node BANK_A --account ACT-A-001 --amount 500.00
    """
    bridge = COBOLBridge(node=node, data_dir=data_dir)
    result = bridge.validate_transaction_via_cobol(account, amount)
    bridge.close()

    if result['status'] == '00':
        click.echo(f"✓ Validation passed: {account} can process ${amount:.2f}")
    else:
        click.echo(f"✗ Validation failed [{result['status']}]: {result['message']}")
        sys.exit(1)


# ── Reports ──────────────────────────────────────────────────────
# Read-only reports generated from transaction and account data.

@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier')
@click.option('--type', 'report_type', type=click.Choice(['STATEMENT', 'LEDGER', 'EOD', 'AUDIT'],
              case_sensitive=False), required=True, help='Report type')
@click.option('--account', default=None, help='Account ID (required for STATEMENT)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def report(node: str, report_type: str, account: str, data_dir: str):
    """Generate a report from node data.

    Report types:
        STATEMENT — Transaction history for one account (requires --account)
        LEDGER    — All transactions across all accounts
        EOD       — End-of-day summary
        AUDIT     — Account listing with chain integrity status

    Example: legacyledger report --node BANK_A --type STATEMENT --account ACT-A-001
    """
    if report_type.upper() == 'STATEMENT' and not account:
        click.echo("Error: --account required for STATEMENT report", err=True)
        sys.exit(1)

    bridge = COBOLBridge(node=node, data_dir=data_dir)
    lines = bridge.get_reports_via_cobol(report_type, account)
    bridge.close()

    click.echo(f"\n{node} {report_type.upper()} Report:")
    click.echo("-" * 70)
    for line in lines:
        click.echo(f"  {line}")
    click.echo("")


# ── Batch Processing ────────────────────────────────────────────
# Process a file of pipe-delimited transactions in one pass.

@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier')
@click.option('--file', 'batch_file', default=None, help='Batch file (default: BATCH-INPUT.DAT)')
@click.option('--user', default='admin', help='User identity for RBAC (default: admin)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def batch(node: str, batch_file: str, user: str, data_dir: str):
    """Process a batch of transactions from a pipe-delimited file.

    File format (one per line):
        ACCOUNT_ID|TYPE|AMOUNT|DESCRIPTION
        ACCOUNT_ID|T|AMOUNT|DESCRIPTION|TARGET_ID  (transfers)

    Example: legacyledger batch --node BANK_A --file transactions.dat
    """
    auth = get_auth_context(user)
    try:
        auth.require_permission("transactions.batch")
    except PermissionError as e:
        click.echo(f"Access denied: {e}", err=True)
        sys.exit(1)

    bridge = COBOLBridge(node=node, data_dir=data_dir)
    result = bridge.process_batch_via_cobol(batch_file)
    bridge.close()

    summary = result.get('summary', {})
    click.echo(f"\n{node} Batch Processing:")
    click.echo(f"  Total:      {summary.get('total', 0)}")
    click.echo(f"  Successful: {summary.get('success', 0)}")
    click.echo(f"  Failed:     {summary.get('failed', 0)}")
    click.echo(f"  Status:     {result['status']}")

    if result.get('output'):
        click.echo("\nDetails:")
        for line in result['output']:
            click.echo(f"  {line}")
    click.echo("")


# ── Integrity Verification ───────────────────────────────────────
# Commands for verifying hash chain integrity on single nodes.

@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def verify_chain(node: str, data_dir: str):
    """Verify integrity chain of a node."""
    bridge = COBOLBridge(node=node, data_dir=data_dir)
    result = bridge.chain.verify_chain()
    bridge.close()

    click.echo(f"\n{node} Chain Verification:")
    click.echo(f"  Valid:           {result['valid']}")
    click.echo(f"  Entries checked: {result['entries_checked']}")
    click.echo(f"  Time:            {result['time_ms']:.1f}ms")
    if not result['valid']:
        click.echo(f"  First break:     {result['first_break']} ({result['break_type']})")
        click.echo(f"  Details:         {result['details']}")
    else:
        click.echo(f"  Status:          ✓ All entries verified")


@cli.command()
def version():
    """Show version."""
    click.echo("cobol-legacy-ledger v1.0.0-phase1")


# ── Inter-Bank Settlement ─────────────────────────────────────────
# Commands that orchestrate transfers across multiple nodes through
# the clearing house. These use SettlementCoordinator.

@cli.command()
@click.option('--from', 'source_spec', required=True, help='Source: BANK_A:ACT-A-001')
@click.option('--to', 'dest_spec', required=True, help='Destination: BANK_B:ACT-B-003')
@click.option('--amount', type=float, required=True, help='Transfer amount')
@click.option('--desc', default='', help='Description')
@click.option('--user', default='admin', help='User identity for RBAC (default: admin)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def transfer(source_spec: str, dest_spec: str, amount: float, desc: str, user: str, data_dir: str):
    """Execute a single inter-bank transfer.

    Example: legacyledger transfer --from BANK_A:ACT-A-001 --to BANK_B:ACT-B-003 --amount 500.00
    """
    auth = get_auth_context(user)
    try:
        auth.require_permission("transactions.process")
    except PermissionError as e:
        click.echo(f"Access denied: {e}", err=True)
        sys.exit(1)

    try:
        source_bank, source_acct = source_spec.split(':')
        dest_bank, dest_acct = dest_spec.split(':')
    except ValueError:
        click.echo("Error: Use format BANK_X:ACT-X-NNN", err=True)
        sys.exit(1)

    coordinator = SettlementCoordinator(data_dir=data_dir)
    result = coordinator.execute_transfer(
        source_bank=source_bank,
        source_account=source_acct,
        dest_bank=dest_bank,
        dest_account=dest_acct,
        amount=amount,
        description=desc or 'Transfer via CLI'
    )

    # Format output -- box-drawing characters for clear visual structure
    click.echo("")
    click.echo("╔══════════════════════════════════════════════════════════════╗")
    click.echo("║  INTER-BANK SETTLEMENT                                      ║")
    click.echo(f"║  REF: {result.settlement_ref:<55}║")
    click.echo("╠══════════════════════════════════════════════════════════════╣")
    click.echo("║                                                              ║")

    if result.steps_completed >= 1:
        click.echo("║  STEP 1: DEBIT SOURCE                                        ║")
        click.echo(f"║    {result.source_bank} / {result.source_account:<20} -${result.amount:>10.2f}                ║")
        click.echo(f"║    TRX: {result.source_trx_id:<24} STATUS: {'OK' if result.source_trx_id else 'FAILED':<6}        ║")
        click.echo("║                                                              ║")

    if result.steps_completed >= 2:
        click.echo("║  STEP 2: CLEARING SETTLEMENT                                 ║")
        click.echo(f"║    CLEARING / NST-{result.source_bank[-1]}        +${result.amount:>10.2f}  (deposit)           ║")
        click.echo(f"║    CLEARING / NST-{result.dest_bank[-1]}        -${result.amount:>10.2f}  (withdrawal)        ║")
        click.echo(f"║    TRX: {result.clearing_deposit_id:<12}, {result.clearing_withdraw_id:<12}  STATUS: OK       ║")
        click.echo("║                                                              ║")

    if result.steps_completed >= 3:
        click.echo("║  STEP 3: CREDIT DESTINATION                                  ║")
        click.echo(f"║    {result.dest_bank} / {result.dest_account:<20} +${result.amount:>10.2f}                ║")
        click.echo(f"║    TRX: {result.dest_trx_id:<24} STATUS: {'OK' if result.dest_trx_id else 'FAILED':<6}        ║")
        click.echo("║                                                              ║")

    click.echo("╠══════════════════════════════════════════════════════════════╣")
    status_display = result.status
    if result.error:
        status_display = f"{result.status}: {result.error[:40]}"
    click.echo(f"║  RESULT: {status_display:<49} ║")
    click.echo(f"║  STEPS: {result.steps_completed}/3   CHAIN ENTRIES: {result.steps_completed}                       ║")
    click.echo("╚══════════════════════════════════════════════════════════════╝")
    click.echo("")


@cli.command()
@click.option('--user', default='admin', help='User identity for RBAC (default: admin)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def settle(user: str, data_dir: str):
    """Execute demo batch settlement across all nodes.

    Runs 8 pre-defined transfers exercising all banks with normal, large,
    and failure scenarios. Shows balance before/after and calculates net positions.
    """
    auth = get_auth_context(user)
    try:
        auth.require_permission("transactions.process")
    except PermissionError as e:
        click.echo(f"Access denied: {e}", err=True)
        sys.exit(1)

    coordinator = SettlementCoordinator(data_dir=data_dir)

    click.echo("")
    click.echo("╔══════════════════════════════════════════════════════════════╗")
    click.echo("║  DEMO BATCH SETTLEMENT                                      ║")
    click.echo("╚══════════════════════════════════════════════════════════════╝")
    click.echo("")
    click.echo(f"Processing {len(DEMO_SETTLEMENT_BATCH)} transfers...")
    click.echo("")

    results = coordinator.execute_batch_settlement(DEMO_SETTLEMENT_BATCH)

    # Display results
    for i, result in enumerate(results, 1):
        status_symbol = "✓" if result.status == "COMPLETED" else "⚠" if result.status == "PARTIAL_FAILURE" else "✗"
        click.echo(f"{status_symbol} [{i}] {result.source_bank}:{result.source_account} → "
                   f"{result.dest_bank}:{result.dest_account} | "
                   f"${result.amount:>8.2f} | {result.settlement_ref} | "
                   f"{result.status}")
        if result.error:
            click.echo(f"      Error: {result.error}")

    # Summary
    summary = coordinator.get_settlement_summary(results)

    click.echo("")
    click.echo("╔══════════════════════════════════════════════════════════════╗")
    click.echo("║  SETTLEMENT SUMMARY                                         ║")
    click.echo("╠══════════════════════════════════════════════════════════════╣")
    click.echo(f"║  Total Transfers:  {summary['total_transfers']:<5}                               ║")
    click.echo(f"║  Completed:        {summary['completed']:<5}                               ║")
    click.echo(f"║  Partial Failure:  {summary['partial']:<5}                               ║")
    click.echo(f"║  Failed:           {summary['failed']:<5}                               ║")
    click.echo("║                                                              ║")
    click.echo("║  NET POSITIONS:                                              ║")
    for bank, net in sorted(summary['net_positions'].items()):
        if bank != 'CLEARING':
            sign = "+" if net >= 0 else "-"
            click.echo(f"║    {bank:<8} {sign}${abs(net):>12.2f}                           ║")
    click.echo("║                                                              ║")
    click.echo("║  NOSTRO POSITIONS:                                           ║")
    for nostro, balance in sorted(summary['nostro_positions'].items()):
        sign = "+" if balance >= 0 else "-"
        click.echo(f"║    {nostro:<12} {sign}${abs(balance):>12.2f}                       ║")
    click.echo("║                                                              ║")
    balance_check = "✓ BALANCED" if summary['clearing_balance_check'] else "✗ MISMATCH"
    click.echo(f"║  NOSTRO NET: ${summary['nostro_net']:>10.2f}  {balance_check:<10}      ║")
    click.echo("╚══════════════════════════════════════════════════════════════╝")
    click.echo("")


# ── Network Status ────────────────────────────────────────────────
# Shows a dashboard-style overview of all 6 nodes.

@cli.command()
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def network_status(data_dir: str):
    """Show all nodes, account counts, and balances."""
    nodes = ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']

    click.echo("")
    click.echo("╔══════════════════════════════════════════════════════════════╗")
    click.echo("║  CLEARING NETWORK STATUS                                    ║")
    click.echo("╠══════════════════════════════════════════════════════════════╣")
    click.echo("║                                                              ║")

    total_bank_balance = 0.0
    total_chain_entries = 0

    for node in nodes[:5]:  # Banks
        try:
            bridge = COBOLBridge(node=node, data_dir=data_dir)
            accounts = bridge.list_accounts()
            total_balance = sum(acct['balance'] for acct in accounts)
            chain_entries = len(bridge.chain.get_chain_for_display())
            bridge.close()

            total_bank_balance += total_balance
            total_chain_entries += chain_entries

            click.echo(f"║  {node:<8} {len(accounts):>1} accounts   Total: ${total_balance:>12.2f}   Chain: {chain_entries:>2} entries ║")
        except Exception as e:
            click.echo(f"║  {node:<8} ERROR: {str(e)[:40]:<40} ║")

    click.echo("║  ────────────────────────────────────────────────────────────  ║")

    # Clearing house -- show balance changes relative to initial funding
    NOSTRO_INITIAL = 10000000.00  # Each nostro starts with $10M working capital
    try:
        bridge = COBOLBridge(node='CLEARING', data_dir=data_dir)
        accounts = bridge.list_accounts()
        chain_entries = len(bridge.chain.get_chain_for_display())
        bridge.close()

        total_chain_entries += chain_entries

        # Calculate net settlement position (change from initial)
        nostro_changes = {}
        for acct in sorted(accounts, key=lambda x: x['id']):
            change = acct['balance'] - NOSTRO_INITIAL
            nostro_changes[acct['id']] = change
        nostro_net = sum(nostro_changes.values())

        click.echo(f"║  CLEARING {len(accounts)} accounts   Net:   ${nostro_net:>12.2f}   Chain: {chain_entries:>2} entries ║")
        click.echo("║                                                              ║")

        # Show individual nostro position changes
        for acct_id, change in sorted(nostro_changes.items()):
            sign = "+" if change >= 0 else "-"
            click.echo(f"║  {acct_id:<12} {sign}${abs(change):>11.2f}                                ║")

        click.echo("║  ────────────────────────────────────────────────────────────  ║")
        balanced = "✓ BALANCED" if abs(nostro_net) < 0.01 else "✗ UNBALANCED"
        click.echo(f"║  NOSTRO NET: ${nostro_net:>10.2f}  {balanced:<14}              ║")
    except Exception as e:
        click.echo(f"║  CLEARING  ERROR: {str(e)[:45]:<45} ║")

    click.echo("║                                                              ║")
    click.echo("╚══════════════════════════════════════════════════════════════╝")
    click.echo("")


# ── Cross-Node Verification ──────────────────────────────────────
# The most important command for demonstrating the integrity layer.
# Runs all three verification layers and presents results.

@cli.command()
@click.option('--cross-node', is_flag=True, default=False, help='Run cross-node verification')
@click.option('--node', default=None, help='Verify single node (default: all)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def verify(cross_node: bool, node: str, data_dir: str):
    """Verify integrity chains. Use --cross-node for full network verification."""
    if cross_node or node is None:
        # Cross-node verification
        verifier = CrossNodeVerifier(data_dir=data_dir)
        report = verifier.verify_all()
        verifier.close()

        click.echo("")
        click.echo("╔══════════════════════════════════════════════════════════════╗")
        click.echo("║  CROSS-NODE INTEGRITY VERIFICATION                          ║")
        click.echo("╠══════════════════════════════════════════════════════════════╣")
        click.echo("║                                                              ║")
        click.echo("║  CHAIN INTEGRITY (SHA-256 hash linkage)                      ║")

        for n in ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']:
            intact = report.chain_integrity.get(n, False)
            entries = report.chain_lengths.get(n, 0)
            status = "✓ INTACT" if intact else "✗ BROKEN"
            click.echo(f"║    {n:<10} {entries:>4} entries   {status:<20}            ║")

        click.echo("║                                                              ║")
        click.echo("║  SETTLEMENT CROSS-REFERENCES                                 ║")
        click.echo(f"║    {report.settlements_checked} settlements verified"
                   f"                                    ║")
        click.echo(f"║    {report.settlements_matched} matched  ·  "
                   f"{report.settlements_partial} partial  ·  "
                   f"{report.settlements_mismatched} mismatched  ·  "
                   f"{report.settlements_orphaned} orphaned   ║")

        # Balance drift section -- detects DAT file tampering
        if report.balance_drift:
            drift_count = sum(len(v) for v in report.balance_drift.values())
            tamper_detected = any(
                'tamper' in issue.lower() for issues in report.balance_drift.values() for issue in issues
            )
            click.echo("║                                                              ║")
            if tamper_detected:
                click.echo(f"║  ⚠ BALANCE TAMPER DETECTED ({drift_count} account(s))                  ║")
            else:
                click.echo(f"║  BALANCE DRIFT ({drift_count} account(s))                               ║")
            shown = 0
            for drift_node, issues in report.balance_drift.items():
                for issue in issues:
                    if shown >= 3:
                        remaining = drift_count - shown
                        click.echo(f"║    ... and {remaining} more                                      ║")
                        break
                    display = issue[:56]
                    click.echo(f"║    {display:<56} ║")
                    shown += 1
                if shown >= 3:
                    break

        # Real anomalies (chain breaks, settlement mismatches -- not balance drift)
        if report.anomalies:
            click.echo("║                                                              ║")
            click.echo("║  ⚠ ANOMALIES DETECTED                                       ║")
            for anomaly in report.anomalies[:5]:
                display = anomaly[:56]
                click.echo(f"║    {display:<56} ║")

            for anomaly in report.anomalies:
                if "chain hash mismatch" in anomaly:
                    click.echo("║                                                              ║")
                    click.echo("║    → Two independent witnesses contradict the tampered ledger ║")
                    break

        click.echo("║                                                              ║")
        click.echo("║  ─────────────────────────────────────────────────────────── ║")
        has_tamper = any(
            'tamper' in issue.lower()
            for issues in report.balance_drift.values() for issue in issues
        ) if report.balance_drift else False

        if has_tamper:
            click.echo("║  ⚠ TAMPER DETECTED  ·  DAT/DB balance mismatch               ║")
        elif report.all_chains_intact and report.all_settlements_matched:
            click.echo("║  ✓ ALL CHAINS INTACT  ·  ALL SETTLEMENTS MATCHED             ║")
        elif report.all_chains_intact and not report.all_settlements_matched:
            click.echo("║  ✓ CHAINS INTACT  ·  settlements have partials (NSF etc)     ║")
        else:
            issues = []
            if not report.all_chains_intact:
                broken = sum(1 for v in report.chain_integrity.values() if not v)
                issues.append(f"{broken} chain(s) broken")
            if not report.all_settlements_matched:
                issues.append(f"{len(report.anomalies)} anomaly(ies)")
            click.echo(f"║  ✗ INTEGRITY VIOLATION  ·  {' · '.join(issues):<33}║")

        click.echo(f"║  Verified in {report.verification_time_ms:.1f}ms"
                   f"{'':>{46 - len(f'{report.verification_time_ms:.1f}')}}║")
        click.echo("╚══════════════════════════════════════════════════════════════╝")
        click.echo("")
    else:
        # Single-node verification
        bridge = COBOLBridge(node=node, data_dir=data_dir)
        result = bridge.chain.verify_chain()
        bridge.close()

        click.echo(f"\n{node} Chain Verification:")
        click.echo(f"  Valid:           {result['valid']}")
        click.echo(f"  Entries checked: {result['entries_checked']}")
        click.echo(f"  Time:            {result['time_ms']:.1f}ms")
        if not result['valid']:
            click.echo(f"  First break:     {result['first_break']} ({result['break_type']})")
        else:
            click.echo(f"  Status:          ✓ All entries verified")


# ── Demo Tamper Command ───────────────────────────────────────────
# Intentionally tampers a DAT file for demonstration purposes.
# Run 'verify --cross-node' after to show the integrity layer catching it.

@cli.command()
@click.option('--node', required=True, help='Node to tamper (e.g., BANK_A)')
@click.option('--type', 'tamper_type', type=click.Choice(['balance']), default='balance',
              help='Type of tamper')
@click.option('--account', required=True, help='Account to tamper (e.g., ACT-A-001)')
@click.option('--amount', type=float, required=True, help='New balance amount')
@click.option('--user', default='admin', help='User identity for RBAC (default: admin)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def tamper_demo(node: str, tamper_type: str, account: str, amount: float, user: str, data_dir: str):
    """DEMO ONLY: Tamper with a node's data to demonstrate integrity detection.

    WARNING: This modifies .DAT files directly, bypassing COBOL and the integrity chain.
    For demonstration purposes only.

    Example: tamper-demo --node BANK_A --account ACT-A-001 --amount 9999.99
    """
    auth = get_auth_context(user)
    try:
        auth.require_permission("node.manage")
    except PermissionError as e:
        click.echo(f"Access denied: {e}", err=True)
        sys.exit(1)

    click.echo("")
    click.echo("⚠  TAMPER DEMO — For demonstration purposes only")
    click.echo(f"   Modifying {node}/{account} balance to ${amount:.2f}")
    click.echo("")

    try:
        result = tamper_balance(data_dir, node, account, amount)
        click.echo(f"   Modified {result['file']}")
        click.echo(f"   {account} balance → ${amount:.2f}")
        click.echo("")
        click.echo("   Run 'verify --cross-node' to detect this tampering.")
        click.echo("")
    except Exception as e:
        click.echo(f"   Error: {e}", err=True)
        sys.exit(1)


# ── Simulation ────────────────────────────────────────────────────
# The simulate command runs a multi-day banking simulation with both
# internal (intra-bank) and external (inter-bank) transactions.
# It orchestrates the full demo workflow: seed -> simulate -> verify.

@cli.command()
@click.option('--days', default=None, type=int, help='Number of days to simulate (default: unlimited)')
@click.option('--time-scale', default=3600, type=int, help='Simulated seconds per real second (default: 3600 = 1 hour/sec)')
@click.option('--tx-per-day', default='25-100', help='Transaction range per day (default: 25-100)')
@click.option('--verify-every', default=5, type=int, help='Run cross-node verification every N days (0=never)')
@click.option('--seed', default=None, type=int, help='Random seed for reproducibility')
@click.option('--output-dir', default=None, help='Log output directory (default: none)')
@click.option('--internal-ratio', default=40, type=int, help='Percentage of internal transactions (default: 40)')
@click.option('--monthly-events/--no-monthly-events', default=True, help='Enable interest+fee processing (default: on)')
@click.option('--scenarios/--no-scenarios', default=True, help='Enable scripted scenario events (default: on)')
@click.option('--relaxed-guards/--safe-guards', default=True, help='Relax safety guards for organic failures (default: relaxed)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def simulate(days, time_scale, tx_per_day, verify_every, seed, output_dir,
             internal_ratio, monthly_events, scenarios, relaxed_guards, data_dir):
    """Run a two-layer banking day simulation.

    Generates realistic daily banking activity across all 5 banks with two layers:
    external inter-bank transfers (settlement) and internal intra-bank operations
    (deposits, withdrawals, transfers, interest, fees).

    Produces 6 log streams when --output-dir is specified:
    SETTLEMENT.log + BANK_A_INTERNAL.log through BANK_E_INTERNAL.log.

    Examples:
        legacyledger simulate --days 30 --seed 42
        legacyledger simulate --days 365 --seed 42 --output-dir logs/
        legacyledger simulate --days 5 --internal-ratio 60 --no-monthly-events
    """
    # Parse tx range
    try:
        parts = tx_per_day.split('-')
        tx_range = (int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        click.echo(f"Error: --tx-per-day must be MIN-MAX (e.g. 25-100)", err=True)
        sys.exit(1)

    mode = f"{days} days" if days else "continuous (Ctrl+C to stop)"
    click.echo(f"\n  Banking Day Simulator")
    click.echo(f"  Mode: {mode} · Scale: 1s = {time_scale}s sim · TX/day: {tx_per_day}")
    click.echo(f"  Internal: {internal_ratio}% · Monthly events: {'on' if monthly_events else 'off'}")
    click.echo(f"  Scenarios: {'on' if scenarios else 'off'} · Guards: {'relaxed' if relaxed_guards else 'safe'}")
    if seed is not None:
        click.echo(f"  Seed: {seed}")
    if output_dir:
        click.echo(f"  Logs: {output_dir}/")

    engine = SimulationEngine(
        data_dir=data_dir,
        time_scale=time_scale,
        tx_range=tx_range,
        verify_every=verify_every,
        seed=seed,
        output_dir=output_dir,
        internal_ratio=internal_ratio,
        monthly_events=monthly_events,
        scenarios=scenarios,
        relaxed_guards=relaxed_guards,
    )
    engine.run(days=days)


# ── Monthly Batch Operations ─────────────────────────────────────
# Interest accrual, fee assessment, and reconciliation for a single node.

@cli.command()
@click.option('--node', required=True, help='Node identifier (e.g., BANK_A)')
@click.option('--user', default='admin', help='User identity for RBAC (default: admin)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def interest(node: str, user: str, data_dir: str):
    """Run interest accrual batch for a node.

    Posts monthly interest to all savings accounts based on tiered rates:
    <$10K = 0.50%, $10K-$100K = 1.50%, >$100K = 2.00% APR.

    Example: legacyledger interest --node BANK_A
    """
    auth = get_auth_context(user)
    try:
        auth.require_permission("transactions.batch")
    except PermissionError as e:
        click.echo(f"Access denied: {e}", err=True)
        sys.exit(1)

    bridge = COBOLBridge(node=node, data_dir=data_dir)
    result = bridge.run_interest_batch()
    bridge.close()

    if result['status'] == '00':
        click.echo(f"\n{node} Interest Accrual:")
        click.echo(f"  Accounts processed: {result['accounts_processed']}")
        click.echo(f"  Total interest:     ${result['total_interest']:.2f}")
        click.echo(f"  Status:             OK")
    else:
        click.echo(f"Error: {result.get('message', 'Unknown error')}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--node', required=True, help='Node identifier (e.g., BANK_A)')
@click.option('--user', default='admin', help='User identity for RBAC (default: admin)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def fees(node: str, user: str, data_dir: str):
    """Run fee assessment batch for a node.

    Assesses monthly maintenance ($12) and low-balance ($8) fees on
    checking accounts. Waived if balance > $5,000. Balance floor protection
    prevents fees from causing negative balances.

    Example: legacyledger fees --node BANK_A
    """
    auth = get_auth_context(user)
    try:
        auth.require_permission("transactions.batch")
    except PermissionError as e:
        click.echo(f"Access denied: {e}", err=True)
        sys.exit(1)

    bridge = COBOLBridge(node=node, data_dir=data_dir)
    result = bridge.run_fee_batch()
    bridge.close()

    if result['status'] == '00':
        click.echo(f"\n{node} Fee Assessment:")
        click.echo(f"  Accounts assessed:  {result['accounts_assessed']}")
        click.echo(f"  Total fees:         ${result['total_fees']:.2f}")
        click.echo(f"  Status:             OK")
    else:
        click.echo(f"Error: {result.get('message', 'Unknown error')}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--node', required=True, help='Node identifier (e.g., BANK_A)')
@click.option('--data-dir', default='COBOL-BANKING/data', help='Data directory')
def reconcile(node: str, data_dir: str):
    """Run balance reconciliation for a node.

    Sums all transactions by account and compares against current balances.
    Reports MATCH or MISMATCH per account.

    Example: legacyledger reconcile --node BANK_A
    """
    bridge = COBOLBridge(node=node, data_dir=data_dir)
    result = bridge.run_reconciliation()
    bridge.close()

    click.echo(f"\n{node} Reconciliation:")
    click.echo(f"  Matched:     {result['matched']}")
    click.echo(f"  Mismatched:  {result['mismatched']}")
    click.echo(f"  Total:       {result['total']}")
    if result['mismatched'] == 0:
        click.echo(f"  Status:      All accounts reconcile")
    else:
        click.echo(f"  Status:      {result['mismatched']} account(s) MISMATCH")
        sys.exit(1)


# ── COBOL Code Generation ─────────────────────────────────────────
# Bi-directional commands: parse, generate, edit, and validate COBOL source.

@cli.command()
@click.argument('filepath')
def cobol_parse(filepath: str):
    """Parse a COBOL source file and display its structure.

    Shows divisions, file declarations, working-storage fields, and paragraphs.

    Example: legacyledger cobol-parse COBOL-BANKING/src/SMOKETEST.cob
    """
    from .cobol_codegen import COBOLParser

    parser = COBOLParser()
    try:
        program = parser.parse_file(filepath)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"\nProgram: {program.metadata.program_id}")
    click.echo(f"  Copybooks: {', '.join(program.copybooks) or 'none'}")
    click.echo("")

    if program.files:
        click.echo("  Files:")
        for f in program.files:
            click.echo(f"    {f.logical_name} -> {f.physical_name}")

    if program.working_storage:
        click.echo("  Working Storage:")
        for item in program.working_storage:
            pic_str = f" PIC {item.pic}" if item.pic else ""
            click.echo(f"    {item.level:02d} {item.name}{pic_str}")
            for cond in item.conditions:
                click.echo(f"        88 {cond.name} VALUE '{cond.value}'")

    if program.paragraphs:
        click.echo("  Paragraphs:")
        for para in program.paragraphs:
            click.echo(f"    {para.name} ({len(para.statements)} statements)")

    click.echo("")


@cli.command()
@click.option('--template', type=click.Choice(['crud', 'report', 'batch']),
              required=True, help='Program template type')
@click.option('--name', required=True, help='Program name (e.g., CUSTOMERS)')
@click.option('--output', default=None, help='Output file (default: stdout)')
def cobol_gen(template: str, name: str, output: str):
    """Generate a new COBOL program from a template.

    Templates:
        crud   — Account-style CRUD program
        report — Read-only report generator
        batch  — Sequential file batch processor

    Example: legacyledger cobol-gen --template crud --name CUSTOMERS --output CUSTOMERS.cob
    """
    from .cobol_codegen import COBOLGenerator, crud_program, report_program, batch_program

    gen = COBOLGenerator()

    if template == 'crud':
        program = crud_program(
            name=name.upper(),
            record_copybook=f"{name.upper()}REC.cpy",
            record_name=f"{name.upper()}-RECORD",
            file_name=f"{name.upper()}.DAT",
            id_field=f"{name.upper()}-ID",
        )
    elif template == 'report':
        program = report_program(
            name=name.upper(),
            input_files=[{
                'logical_name': f"{name.upper()}-FILE",
                'physical_name': f"{name.upper()}.DAT",
                'copybook': f"{name.upper()}REC.cpy",
            }],
            report_types=["SUMMARY", "DETAIL"],
        )
    elif template == 'batch':
        program = batch_program(
            name=name.upper(),
            input_file=f"{name.upper()}-INPUT.DAT",
            input_copybook=f"{name.upper()}REC.cpy",
            record_name=f"{name.upper()}-RECORD",
        )

    source = gen.generate(program)

    if output:
        Path(output).write_text(source, encoding='utf-8')
        click.echo(f"Generated {output} ({len(source)} bytes)")
    else:
        click.echo(source)


def _find_parent_of(program, child_name: str):
    """Find the parent group item that contains a child with the given name."""
    from python.cobol_codegen.ast_nodes import DataItem

    def _search(item: DataItem) -> str:
        for child in item.children:
            if child.name == child_name:
                return item.name
            found = _search(child)
            if found:
                return found
        return None

    for f in program.files:
        for rec in f.record_fields:
            found = _search(rec)
            if found:
                return found
    for item in program.working_storage:
        found = _search(item)
        if found:
            return found
    return None


@cli.command()
@click.argument('filepath')
@click.option('--add-field', nargs=2, default=None, help='Add field: NAME "PIC X(n)"')
@click.option('--after', default=None, help='Insert after this field')
@click.option('--remove-field', default=None, help='Remove field by name')
@click.option('--rename-para', nargs=2, default=None, help='Rename paragraph: OLD NEW')
@click.option('--output', default=None, help='Output file (default: overwrite)')
def cobol_edit(filepath: str, add_field, after: str, remove_field: str,
               rename_para, output: str):
    """Apply an edit operation to an existing COBOL file.

    Examples:
        legacyledger cobol-edit ACCOUNTS.cob --add-field ACCT-EMAIL "X(50)" --after ACCT-NAME
        legacyledger cobol-edit ACCOUNTS.cob --remove-field ACCT-EMAIL
        legacyledger cobol-edit ACCOUNTS.cob --rename-para OLD-NAME NEW-NAME
    """
    from .cobol_codegen import COBOLParser, COBOLGenerator, COBOLEditor

    parser = COBOLParser()
    try:
        program = parser.parse_file(filepath)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    editor = COBOLEditor()
    result_msg = ""

    if add_field:
        name, pic = add_field
        parent_name = None

        # If --after is specified, find the parent that contains that field
        if after:
            parent_name = _find_parent_of(program, after)

        # Otherwise, use heuristic: first file record, then first WS group
        if not parent_name:
            for f in program.files:
                if f.record_fields:
                    parent_name = f.record_fields[0].name
                    break
        if not parent_name:
            for item in program.working_storage:
                if item.is_group:
                    parent_name = item.name
                    break

        if parent_name:
            result_msg = editor.add_field(program, parent_name, name, pic, after=after)
        else:
            result_msg = "Error: no group item found to add field to"

    elif remove_field:
        result_msg = editor.remove_field(program, remove_field)

    elif rename_para:
        old_name, new_name = rename_para
        result_msg = editor.rename_paragraph(program, old_name, new_name)

    else:
        click.echo("Error: specify an edit operation (--add-field, --remove-field, --rename-para)", err=True)
        sys.exit(1)

    click.echo(result_msg)

    gen = COBOLGenerator()
    source = gen.generate(program)
    out_path = output or filepath
    Path(out_path).write_text(source, encoding='utf-8')
    click.echo(f"Written to {out_path}")


@cli.command()
@click.argument('filepath')
def cobol_validate(filepath: str):
    """Run convention validator on a COBOL file.

    Checks naming conventions, PIC clause semantics, paragraph structure,
    and other project-specific rules. Reports issues with severity.

    Example: legacyledger cobol-validate COBOL-BANKING/src/ACCOUNTS.cob
    """
    from .cobol_codegen import COBOLParser, COBOLValidator

    parser = COBOLParser()
    try:
        program = parser.parse_file(filepath)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    validator = COBOLValidator()
    issues = validator.validate(program)

    click.echo(f"\nValidation: {filepath}")
    click.echo(f"  Program: {program.metadata.program_id}")
    click.echo(f"  Issues:  {len(issues)}")
    click.echo("")

    if issues:
        for issue in issues:
            click.echo(f"  {issue}")
        errors = sum(1 for i in issues if i.severity == "ERROR")
        warnings = sum(1 for i in issues if i.severity == "WARNING")
        click.echo(f"\n  {errors} error(s), {warnings} warning(s)")
        if errors > 0:
            sys.exit(1)
    else:
        click.echo("  All conventions met")

    click.echo("")


if __name__ == '__main__':
    cli()
