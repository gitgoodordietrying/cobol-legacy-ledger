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

    coordinator = SettlementCoordinator(project_root=str(Path(data_dir).parent))
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
    coordinator = SettlementCoordinator(project_root=str(Path(data_dir).parent))

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

    # Clearing house
    try:
        bridge = COBOLBridge(node='CLEARING', data_dir=data_dir)
        accounts = bridge.list_accounts()
        nostro_net = sum(acct['balance'] for acct in accounts)
        chain_entries = len(bridge.chain.get_chain_for_display())
        bridge.close()

        total_chain_entries += chain_entries

        click.echo(f"║  CLEARING 5 accounts   Net:   ${nostro_net:>12.2f}   Chain: {chain_entries:>2} entries ║")
        click.echo("║                                                              ║")

        # Show individual nostro balances
        for acct in sorted(accounts, key=lambda x: x['id']):
            click.echo(f"║  {acct['id']:<10} {acct['balance']:>12.2f}                                    ║")

        click.echo("║  ────────────────────────────────────────────────────────────  ║")
        balanced = "✓ BALANCED" if abs(nostro_net) < 0.01 else "✗ UNBALANCED"
        click.echo(f"║  NOSTRO NET: ${nostro_net:>10.2f}  {balanced:<14}              ║")
    except Exception as e:
        click.echo(f"║  CLEARING  ERROR: {str(e)[:45]:<45} ║")

    click.echo("║                                                              ║")
    click.echo("╚══════════════════════════════════════════════════════════════╝")
    click.echo("")


if __name__ == '__main__':
    cli()
