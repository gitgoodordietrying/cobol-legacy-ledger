"""
CLI commands for cobol-legacy-ledger.
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


@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier (BANK_A, BANK_B, ..., CLEARING)')
@click.option('--data-dir', default='banks', help='Data directory')
def init_db(node: str, data_dir: str):
    """Initialize database and integrity chain for a node."""
    click.echo(f"Initializing {node} database...")

    bridge = COBOLBridge(node=node, data_dir=data_dir)
    bridge.seed_demo_data()
    bridge.close()

    click.echo(f"✓ {node} initialized at {data_dir}/{node.lower()}/")


@cli.command()
@click.option('--data-dir', default='banks', help='Data directory')
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


@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier')
@click.option('--data-dir', default='banks', help='Data directory')
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
@click.option('--data-dir', default='banks', help='Data directory')
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


@cli.command()
@click.option('--node', default='BANK_A', help='Source node')
@click.option('--account-id', prompt='Account ID', help='Source account')
@click.option('--tx-type', type=click.Choice(['D', 'W', 'T'], case_sensitive=False),
              prompt='Type (D=deposit, W=withdraw, T=transfer)', help='Transaction type')
@click.option('--amount', prompt='Amount', type=float, help='Amount')
@click.option('--description', prompt='Description', default='CLI transaction', help='Description')
@click.option('--target-id', default=None, help='Target account (for transfers)')
@click.option('--data-dir', default='banks', help='Data directory')
def transact(node: str, account_id: str, tx_type: str, amount: float, description: str,
             target_id: str, data_dir: str):
    """Process a transaction."""
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


@cli.command()
@click.option('--node', default='BANK_A', help='Node identifier')
@click.option('--data-dir', default='banks', help='Data directory')
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


@cli.command()
@click.option('--from', 'source_spec', required=True, help='Source: BANK_A:ACT-A-001')
@click.option('--to', 'dest_spec', required=True, help='Destination: BANK_B:ACT-B-003')
@click.option('--amount', type=float, required=True, help='Transfer amount')
@click.option('--desc', default='', help='Description')
@click.option('--data-dir', default='banks', help='Data directory')
def transfer(source_spec: str, dest_spec: str, amount: float, desc: str, data_dir: str):
    """Execute a single inter-bank transfer.

    Example: legacyledger transfer --from BANK_A:ACT-A-001 --to BANK_B:ACT-B-003 --amount 500.00
    """
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

    # Format output
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
@click.option('--data-dir', default='banks', help='Data directory')
def settle(data_dir: str):
    """Execute demo batch settlement across all nodes.

    Runs 8 pre-defined transfers exercising all banks with normal, large,
    and failure scenarios. Shows balance before/after and calculates net positions.
    """
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


@cli.command()
@click.option('--data-dir', default='banks', help='Data directory')
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

    # Clearing house — show balance changes relative to initial funding
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


@cli.command()
@click.option('--cross-node', is_flag=True, default=False, help='Run cross-node verification')
@click.option('--node', default=None, help='Verify single node (default: all)')
@click.option('--data-dir', default='banks', help='Data directory')
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

        # Balance drift section — detects DAT file tampering
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

        # Real anomalies (chain breaks, settlement mismatches — not balance drift)
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


@cli.command()
@click.option('--node', required=True, help='Node to tamper (e.g., BANK_A)')
@click.option('--type', 'tamper_type', type=click.Choice(['balance']), default='balance',
              help='Type of tamper')
@click.option('--account', required=True, help='Account to tamper (e.g., ACT-A-001)')
@click.option('--amount', type=float, required=True, help='New balance amount')
@click.option('--data-dir', default='banks', help='Data directory')
def tamper_demo(node: str, tamper_type: str, account: str, amount: float, data_dir: str):
    """DEMO ONLY: Tamper with a node's data to demonstrate integrity detection.

    WARNING: This modifies .DAT files directly, bypassing COBOL and the integrity chain.
    For demonstration purposes only.

    Example: tamper-demo --node BANK_A --account ACT-A-001 --amount 9999.99
    """
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


@cli.command()
@click.option('--days', default=None, type=int, help='Number of days to simulate (default: unlimited)')
@click.option('--time-scale', default=3600, type=int, help='Simulated seconds per real second (default: 3600 = 1 hour/sec)')
@click.option('--tx-per-day', default='25-100', help='Transaction range per day (default: 25-100)')
@click.option('--verify-every', default=5, type=int, help='Run cross-node verification every N days (0=never)')
@click.option('--seed', default=None, type=int, help='Random seed for reproducibility')
@click.option('--output-dir', default=None, help='Log output directory (default: none)')
@click.option('--internal-ratio', default=40, type=int, help='Percentage of internal transactions (default: 40)')
@click.option('--monthly-events/--no-monthly-events', default=True, help='Enable interest+fee processing (default: on)')
@click.option('--data-dir', default='banks', help='Data directory')
def simulate(days, time_scale, tx_per_day, verify_every, seed, output_dir,
             internal_ratio, monthly_events, data_dir):
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
    )
    engine.run(days=days)


@cli.command()
@click.option('--node', required=True, help='Node identifier (e.g., BANK_A)')
@click.option('--data-dir', default='banks', help='Data directory')
def interest(node: str, data_dir: str):
    """Run interest accrual batch for a node.

    Posts monthly interest to all savings accounts based on tiered rates:
    <$10K = 0.50%, $10K-$100K = 1.50%, >$100K = 2.00% APR.

    Example: legacyledger interest --node BANK_A
    """
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
@click.option('--data-dir', default='banks', help='Data directory')
def fees(node: str, data_dir: str):
    """Run fee assessment batch for a node.

    Assesses monthly maintenance ($12) and low-balance ($8) fees on
    checking accounts. Waived if balance > $5,000. Balance floor protection
    prevents fees from causing negative balances.

    Example: legacyledger fees --node BANK_A
    """
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
@click.option('--data-dir', default='banks', help='Data directory')
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


if __name__ == '__main__':
    cli()
