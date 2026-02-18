"""
CLI commands for cobol-legacy-ledger.
Entry point: python -m bridge cli <command> [args]
"""

import click
import sys
from pathlib import Path
from .bridge import COBOLBridge
from .auth import Role, get_auth_context


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


if __name__ == '__main__':
    cli()
