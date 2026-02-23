"""Quick settlement test script."""
from python.settlement import SettlementCoordinator, DEMO_SETTLEMENT_BATCH

coord = SettlementCoordinator(data_dir='banks')
results = coord.execute_batch_settlement(DEMO_SETTLEMENT_BATCH)

for i, r in enumerate(results, 1):
    sym = 'OK' if r.status == 'COMPLETED' else 'WARN' if r.status == 'PARTIAL_FAILURE' else 'FAIL'
    print(f'[{sym}] #{i} {r.source_bank}:{r.source_account} -> {r.dest_bank}:{r.dest_account} ${r.amount:.2f} | {r.status} | Steps:{r.steps_completed}')
    if r.error:
        print(f'       Error: {r.error}')

summary = coord.get_settlement_summary(results)
print()
print(f"Total: {summary['total_transfers']}  Completed: {summary['completed']}  Failed: {summary['failed']}  Partial: {summary['partial']}")
print(f"Nostro Net: ${summary['nostro_net']:.2f}  Balanced: {summary['clearing_balance_check']}")
print()
for nostro, bal in sorted(summary['nostro_positions'].items()):
    print(f"  {nostro}: {bal:+.2f}")
