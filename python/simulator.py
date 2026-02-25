"""
simulator.py -- Two-layer banking day simulator for the COBOL settlement network.

This module generates realistic daily banking activity across all 5 banks,
producing a rich dataset for demonstrating the integrity verification system.
It operates in two layers:

    Layer 1 -- External (inter-bank): Transfers between different banks flow
    through the clearing house using the SettlementCoordinator. Each transfer
    creates entries in 3 separate integrity chains (source, clearing, destination).

    Layer 2 -- Internal (intra-bank): Deposits, withdrawals, and transfers
    within a single bank. These exercise the COBOLBridge directly without
    settlement coordination.

Bank personalities:
    Each bank has a distinct profile that determines transaction frequency,
    size ranges, and description text. BANK_A is retail (small, frequent),
    BANK_B is corporate (large, less frequent), BANK_D is institutional
    (very large, infrequent), etc. This produces realistic-looking data.

Deterministic seeding:
    The --seed flag makes simulations reproducible. With the same seed, the
    same sequence of random transactions is generated every time. This is
    essential for debugging and for producing consistent demo outputs.

Time scaling:
    The --time-scale flag controls how fast simulated time passes relative
    to wall clock time. At the default 3600, one real second equals one
    simulated hour. Set to 0 for maximum speed (no sleeping).

Scenario layer:
    Pre-scripted events (account freeze, balance tamper, structuring patterns)
    are scheduled at specific simulation days. These create the "interesting"
    moments that make the demo compelling -- the integrity system catches the
    tamper, the frozen account rejects transfers, etc.

Usage:
    python -m python.cli simulate --days 30 --seed 42
    python -m python.cli simulate --days 365 --seed 42 --output-dir logs/
"""

import csv
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional, TextIO

from dataclasses import dataclass, field
from math import ceil

from .settlement import SettlementCoordinator
from .cross_verify import CrossNodeVerifier, tamper_balance


# ── Bank Personality Profiles ─────────────────────────────────────
# Each bank has a distinct transaction profile that determines:
#   - min/max: range for inter-bank transfer amounts
#   - weight: how likely this bank is to initiate external transfers
#   - payroll_freq/min/max: internal deposit patterns
#   - bill_min/max: internal withdrawal patterns
#   - descriptions: realistic text for each transaction type
#
# These profiles produce data that looks like real banking activity,
# making the demo more convincing and the logs more readable.

BANK_PROFILES = {
    'BANK_A': {
        'label': 'retail',
        'min': 50, 'max': 2000, 'weight': 1.4,
        'payroll_freq': 'biweekly', 'payroll_min': 1500, 'payroll_max': 4500,
        'bill_min': 25, 'bill_max': 350,
        'internal_xfer_min': 100, 'internal_xfer_max': 2000,
        'descriptions': {
            'payroll': ["Payroll deposit — Santos", "Payroll deposit — Chen",
                        "Payroll deposit — Williams", "Direct deposit — Park",
                        "Salary deposit — Okafor"],
            'bill': ["Electric bill PMT", "Cable subscription", "Phone bill",
                     "Water utility", "Internet service", "Gym membership",
                     "Streaming subscription", "Insurance premium"],
            'xfer': ["Checking to savings", "Savings to checking",
                     "Emergency fund transfer", "Vacation fund deposit"],
        },
    },
    'BANK_B': {
        'label': 'corporate',
        'min': 1000, 'max': 25000, 'weight': 1.0,
        'payroll_freq': 'biweekly', 'payroll_min': 8000, 'payroll_max': 35000,
        'bill_min': 500, 'bill_max': 5000,
        'internal_xfer_min': 2000, 'internal_xfer_max': 20000,
        'descriptions': {
            'payroll': ["Corp payroll run", "Executive comp deposit",
                        "Contractor payment", "Bonus disbursement"],
            'bill': ["Vendor invoice PMT", "Lease payment", "SaaS subscription",
                     "Legal retainer", "Office supplies", "Cloud hosting"],
            'xfer': ["Operating to reserve", "Reserve to operating",
                     "Capital allocation", "Treasury sweep"],
        },
    },
    'BANK_C': {
        'label': 'wealth mgmt',
        'min': 500, 'max': 15000, 'weight': 1.0,
        'payroll_freq': 'monthly', 'payroll_min': 5000, 'payroll_max': 25000,
        'bill_min': 200, 'bill_max': 3000,
        'internal_xfer_min': 5000, 'internal_xfer_max': 50000,
        'descriptions': {
            'payroll': ["Quarterly dividend", "Trust distribution",
                        "Advisory fee rebate", "Portfolio income"],
            'bill': ["Advisory fee", "Custodian fee", "Wire fee",
                     "Account maintenance", "Tax preparation"],
            'xfer': ["Portfolio rebalance", "Tax-loss harvest proceeds",
                     "Margin account funding", "CD maturity rollover"],
        },
    },
    'BANK_D': {
        'label': 'institutional',
        'min': 5000, 'max': 45000, 'weight': 0.6,
        'payroll_freq': 'monthly', 'payroll_min': 15000, 'payroll_max': 45000,
        'bill_min': 2000, 'bill_max': 15000,
        'internal_xfer_min': 10000, 'internal_xfer_max': 40000,
        'descriptions': {
            'payroll': ["Trust fund distribution", "Endowment payout",
                        "Pension disbursement", "Foundation grant"],
            'bill': ["Fiduciary fee", "Audit expense", "Compliance cost",
                     "Regulatory assessment", "Custodial services"],
            'xfer': ["Institutional rebalance", "Liquidity management",
                     "Duration matching", "Collateral posting"],
        },
    },
    'BANK_E': {
        'label': 'community',
        'min': 100, 'max': 5000, 'weight': 1.0,
        'payroll_freq': 'biweekly', 'payroll_min': 1200, 'payroll_max': 3500,
        'bill_min': 15, 'bill_max': 250,
        'internal_xfer_min': 50, 'internal_xfer_max': 1500,
        'descriptions': {
            'payroll': ["Grant disbursement", "Donation deposit",
                        "Cooperative dividend", "Stipend payment",
                        "Community share payout"],
            'bill': ["Co-op fee", "Community dues", "Utility PMT",
                     "Rent payment", "Local vendor PMT"],
            'xfer': ["Share account transfer", "Holiday club deposit",
                     "Youth savings deposit", "Emergency fund"],
        },
    },
}

BANKS = list(BANK_PROFILES.keys())

# External transfer descriptions (inter-bank)
EXTERNAL_DESCRIPTIONS = [
    "Wire transfer", "Invoice PMT", "Payroll", "Vendor payment",
    "Loan repayment", "Insurance premium", "Equipment lease",
    "Consulting fee", "Quarterly dividend", "Service charge",
    "Account funding", "Trade settlement", "Refund",
    "Subscription PMT", "Maintenance fee", "Commission",
]

# ── Near-CTR Threshold ────────────────────────────────────────────
# 5% of inter-bank transfers are generated in the $9,000-$9,999 range,
# just below the $10,000 Currency Transaction Report threshold. This
# creates "structuring" patterns that a real compliance system would flag.
NEAR_CTR_CHANCE = 0.05  # 5% chance of near-CTR amount ($9,000-$9,999)


# ── Log Management ────────────────────────────────────────────────
# The simulator produces 6 log streams: 1 settlement log (inter-bank)
# and 5 internal logs (one per bank). Each stream gets both a .log file
# (human-readable) and a .csv file (machine-parseable).

class SimulationLogger:
    """Manages 6 output log streams: 1 settlement + 5 bank internals."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else None
        self._log_files: Dict[str, TextIO] = {}
        self._csv_writers: Dict[str, csv.writer] = {}
        self._csv_files: Dict[str, TextIO] = {}

        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self._open_files()

    def _open_files(self):
        """Open all 6 log files + 6 CSV files."""
        streams = ['SETTLEMENT'] + [f'{b}_INTERNAL' for b in BANKS]
        for name in streams:
            log_path = self.output_dir / f"{name}.log"
            csv_path = self.output_dir / f"{name}.csv"
            self._log_files[name] = open(log_path, 'w', encoding='utf-8')
            self._csv_files[name] = open(csv_path, 'w', newline='', encoding='utf-8')
            self._csv_writers[name] = csv.writer(self._csv_files[name])
            # CSV headers
            self._csv_writers[name].writerow([
                'day', 'date', 'time', 'type', 'source_bank', 'source_account',
                'dest_bank', 'dest_account', 'amount', 'status', 'description', 'ref'
            ])

    def log(self, stream: str, message: str):
        """Write to a log stream."""
        if stream in self._log_files:
            self._log_files[stream].write(message + '\n')

    def log_csv(self, stream: str, row: list):
        """Write a CSV row to a stream."""
        if stream in self._csv_writers:
            self._csv_writers[stream].writerow(row)

    def log_day_header(self, stream: str, day_num: int, date_str: str):
        """Write a day header to a log stream."""
        header = f"\n{'=' * 3} DAY {day_num} | {date_str} {'=' * (52 - len(date_str) - len(str(day_num)))}"
        self.log(stream, header)

    def log_eod_summary(self, stream: str, completed: int, failed: int, volume: float):
        """Write EOD summary to a log stream."""
        self.log(stream, f"  -- EOD Summary {'-' * 50}")
        self.log(stream, f"  {completed} completed | {failed} failed | ${volume:,.2f} volume")

    def log_monthly_summary(self, stream: str, month: str, interest: float,
                            fees: float, internal_count: int, external_count: int):
        """Write monthly summary block."""
        self.log(stream, "")
        self.log(stream, f"  === MONTHLY SUMMARY — {month} ===")
        self.log(stream, f"  Interest accrued:  ${interest:,.2f}")
        self.log(stream, f"  Fees collected:    ${fees:,.2f}")
        self.log(stream, f"  Internal txns:     {internal_count}")
        self.log(stream, f"  External txns:     {external_count}")
        self.log(stream, f"  {'=' * 40}")

    def flush(self):
        """Flush all open file handles to disk."""
        for f in self._log_files.values():
            f.flush()
        for f in self._csv_files.values():
            f.flush()

    def close(self):
        """Close all open files."""
        for f in self._log_files.values():
            f.close()
        for f in self._csv_files.values():
            f.close()


# ── Scenario Layer ────────────────────────────────────────────────
# Pre-scripted events that create "interesting" moments in the simulation.
# These events are scheduled at specific days and fire automatically.
# The scenario director scales the schedule to match the simulation length.


class EventType:
    """String constants for scripted simulation events."""
    FREEZE_ACCOUNT = "FREEZE_ACCOUNT"
    CLOSE_ACCOUNT = "CLOSE_ACCOUNT"
    TAMPER_BALANCE = "TAMPER_BALANCE"
    LARGE_TRANSFER = "LARGE_TRANSFER"
    DRAIN_TRANSFERS = "DRAIN_TRANSFERS"
    SUSPICIOUS_BURST = "SUSPICIOUS_BURST"


@dataclass
class SimulationEvent:
    """A scripted event scheduled for a specific simulation day."""
    day: int
    event_type: str
    params: Dict = field(default_factory=dict)
    description: str = ""
    fired: bool = False


class ScenarioDirector:
    """
    Builds an event schedule scaled to the simulation length.

    The base schedule is designed for a 25-day simulation. For longer
    simulations, events are distributed across three narrative arcs:
        Arc 1 (0-30%): Early anomalies (large transfer, suspicious burst)
        Arc 2 (30-60%): Crisis (balance tamper, drain transfers)
        Arc 3 (60-100%): Resolution (account closure)

    For 180+ day simulations, additional events are added to keep things
    interesting throughout the run.
    """

    # 25-day base schedule (days are 1-indexed)
    BASE_SCHEDULE = [
        SimulationEvent(
            day=3, event_type=EventType.LARGE_TRANSFER,
            params={'source_bank': 'BANK_B', 'source_account': 'ACT-B-001',
                    'dest_bank': 'BANK_D', 'dest_account': 'ACT-D-001',
                    'amount': 55000.00},
            description="$55,000 wire attempted — exceeds $50K daily limit",
        ),
        SimulationEvent(
            day=5, event_type=EventType.SUSPICIOUS_BURST,
            params={'bank': 'BANK_A', 'account': 'ACT-A-001',
                    'count': 8, 'min_amount': 9000, 'max_amount': 9999},
            description="8 near-CTR deposits ($9,000-$9,999) — structuring pattern",
        ),
        SimulationEvent(
            day=7, event_type=EventType.FREEZE_ACCOUNT,
            params={'bank': 'BANK_C', 'account': 'ACT-C-005'},
            description="Regulatory hold — suspicious activity flagged by compliance",
        ),
        SimulationEvent(
            day=10, event_type=EventType.TAMPER_BALANCE,
            params={'bank': 'BANK_C', 'account': 'ACT-C-001',
                    'amount': 999999.99},
            description="Balance set to $999,999.99 via direct DAT edit (tamper)",
        ),
        SimulationEvent(
            day=12, event_type=EventType.DRAIN_TRANSFERS,
            params={'bank': 'BANK_A', 'account': 'ACT-A-003',
                    'dest_account': 'ACT-A-001', 'count': 5, 'amount': 300.00},
            description="5 transfers from low-balance account — NSF cascade expected",
        ),
        SimulationEvent(
            day=15, event_type=EventType.CLOSE_ACCOUNT,
            params={'bank': 'BANK_A', 'account': 'ACT-A-007'},
            description="Account closed — future transactions will fail",
        ),
    ]

    def __init__(self, total_days: int):
        self.total_days = total_days
        self.events = self._build_schedule()

    def _build_schedule(self) -> List[SimulationEvent]:
        """Scale the base schedule to the simulation length."""
        if self.total_days <= 30:
            # Use base schedule as-is, clamping to total_days
            return [
                SimulationEvent(
                    day=e.day, event_type=e.event_type,
                    params=dict(e.params), description=e.description,
                )
                for e in self.BASE_SCHEDULE if e.day <= self.total_days
            ]

        # For longer sims, scale events proportionally across 3 arcs
        scale = self.total_days / 25.0
        events = []

        # Arc 1: Early anomalies (first 30%)
        arc1_end = int(self.total_days * 0.3)
        for e in self.BASE_SCHEDULE[:3]:
            scaled_day = max(2, int(e.day * scale * 0.3))
            if scaled_day <= arc1_end:
                events.append(SimulationEvent(
                    day=scaled_day, event_type=e.event_type,
                    params=dict(e.params), description=e.description,
                ))

        # Arc 2: Crisis (30%-60%)
        arc2_start = arc1_end + 1
        arc2_end = int(self.total_days * 0.6)
        crisis_events = self.BASE_SCHEDULE[3:5]  # tamper + drain
        for i, e in enumerate(crisis_events):
            scaled_day = arc2_start + int((arc2_end - arc2_start) * (i + 1) / (len(crisis_events) + 1))
            events.append(SimulationEvent(
                day=scaled_day, event_type=e.event_type,
                params=dict(e.params), description=e.description,
            ))

        # Arc 3: Resolution (60%-100%)
        arc3_start = arc2_end + 1
        close_event = self.BASE_SCHEDULE[5]  # close account
        events.append(SimulationEvent(
            day=arc3_start + int((self.total_days - arc3_start) * 0.3),
            event_type=close_event.event_type,
            params=dict(close_event.params), description=close_event.description,
        ))

        # Add repeat crisis events for longer simulations
        if self.total_days >= 180:
            mid = self.total_days // 2
            events.append(SimulationEvent(
                day=mid, event_type=EventType.SUSPICIOUS_BURST,
                params={'bank': 'BANK_E', 'account': 'ACT-E-002',
                        'count': 6, 'min_amount': 9000, 'max_amount': 9999},
                description="Second structuring pattern detected at community bank",
            ))
            events.append(SimulationEvent(
                day=mid + 15, event_type=EventType.FREEZE_ACCOUNT,
                params={'bank': 'BANK_E', 'account': 'ACT-E-002'},
                description="Regulatory freeze following structuring detection",
            ))

        events.sort(key=lambda e: e.day)
        return events

    def get_events_for_day(self, day_num: int) -> List[SimulationEvent]:
        """Return unfired events scheduled for this day."""
        return [e for e in self.events if e.day == day_num and not e.fired]

    def has_tamper_fired(self) -> bool:
        """Check if any tamper event has been executed."""
        return any(e.event_type == EventType.TAMPER_BALANCE and e.fired for e in self.events)

    def get_tamper_params(self) -> Optional[Dict]:
        """Return params of the fired tamper event, if any."""
        for e in self.events:
            if e.event_type == EventType.TAMPER_BALANCE and e.fired:
                return e.params
        return None


# ── Simulation Engine ─────────────────────────────────────────────
# The main simulation loop. Each "day" consists of:
#   1. Monthly events (fees on 1st business day, interest on last)
#   2. Scenario events (pre-scripted, if any are scheduled for today)
#   3. Random transactions (mix of internal and external)
#   4. Periodic verification (every N days)
#   5. Periodic reconciliation (every 30 days)

class SimulationEngine:
    """Generates and executes realistic banking days across the settlement network."""

    def __init__(
        self,
        data_dir: str = "COBOL-BANKING/data",
        time_scale: int = 3600,
        tx_range: Tuple[int, int] = (25, 100),
        verify_every: int = 5,
        seed: Optional[int] = None,
        output_dir: Optional[str] = None,
        internal_ratio: int = 40,
        monthly_events: bool = True,
        scenarios: bool = True,
        relaxed_guards: bool = True,
    ):
        self.data_dir = data_dir
        self.time_scale = time_scale
        self.tx_min, self.tx_max = tx_range
        self.verify_every = verify_every
        # Deterministic RNG: same seed = same simulation every time
        self.rng = random.Random(seed)
        self.output_dir = output_dir
        self.internal_ratio = internal_ratio
        self.monthly_events = monthly_events
        self.scenarios = scenarios
        # Relaxed guards allow more organic failures (NSF from normal activity)
        # Safe guards aggressively avoid NSF by checking balances more carefully
        self.relaxed_guards = relaxed_guards

        self.coordinator = SettlementCoordinator(data_dir=data_dir)
        self._account_cache: Dict[str, List[Dict]] = {}
        self._stopped = False

        # Scenario director (built when run() knows total days)
        self.director: Optional[ScenarioDirector] = None

        # Logger
        self.logger = SimulationLogger(output_dir=output_dir)

        # Stats
        self.total_completed = 0
        self.total_failed = 0
        self.total_volume = 0.0
        self.total_internal = 0
        self.total_external = 0
        self.days_run = 0

        # Monthly tracking
        self._current_month = None
        self._monthly_interest: Dict[str, float] = {b: 0.0 for b in BANKS}
        self._monthly_fees: Dict[str, float] = {b: 0.0 for b in BANKS}
        self._monthly_internal_count: Dict[str, int] = {b: 0 for b in BANKS}
        self._monthly_external_count: Dict[str, int] = {b: 0 for b in BANKS}
        self._fees_run_months: set = set()
        self._interest_run_months: set = set()

    def _load_accounts(self):
        """Cache account lists from all banks."""
        for bank in BANKS:
            bridge = self.coordinator.nodes[bank]
            self._account_cache[bank] = bridge.list_accounts()

    def _refresh_account(self, bank: str, account_id: str) -> Optional[Dict]:
        """Get fresh balance for a single account."""
        bridge = self.coordinator.nodes[bank]
        return bridge.get_account(account_id)

    # ── Transaction Generation ────────────────────────────────────
    # These methods generate random but realistic transactions based on
    # bank profiles. They check balances to reduce (but not eliminate)
    # NSF failures, making the simulation more realistic.

    def _pick_external_transfer(self) -> Optional[Dict]:
        """Generate a random inter-bank transfer, checking balances to reduce NSF."""
        weights = [BANK_PROFILES[b]['weight'] for b in BANKS]
        source_bank = self.rng.choices(BANKS, weights=weights, k=1)[0]
        dest_bank = self.rng.choice([b for b in BANKS if b != source_bank])

        source_accounts = self._account_cache.get(source_bank, [])
        dest_accounts = self._account_cache.get(dest_bank, [])
        if not source_accounts or not dest_accounts:
            return None

        profile = BANK_PROFILES[source_bank]
        if self.rng.random() < NEAR_CTR_CHANCE:
            amount = round(self.rng.uniform(9000, 9999), 2)
        else:
            amount = round(self.rng.uniform(profile['min'], profile['max']), 2)

        source_acct = None
        retries = 1 if self.relaxed_guards else 3
        for _ in range(retries):
            candidate = self.rng.choice(source_accounts)
            fresh = self._refresh_account(source_bank, candidate['id'])
            if fresh and fresh['balance'] >= amount and fresh['status'] == 'A':
                source_acct = fresh
                break

        if not source_acct:
            source_acct = self.rng.choice(source_accounts)

        dest_acct = self.rng.choice(dest_accounts)
        desc = self.rng.choice(EXTERNAL_DESCRIPTIONS)

        return {
            'source_bank': source_bank,
            'source_account': source_acct['id'],
            'dest_bank': dest_bank,
            'dest_account': dest_acct['id'],
            'amount': amount,
            'description': desc,
        }

    def _pick_internal_transaction(self, bank: str) -> Optional[Dict]:
        """Generate a random internal transaction for a specific bank.

        Transaction type distribution: 40% deposit, 30% withdrawal, 30% transfer.
        This mix ensures accounts generally grow (more deposits than withdrawals)
        while still producing enough withdrawals for realistic activity.
        """
        profile = BANK_PROFILES[bank]
        accounts = self._account_cache.get(bank, [])
        if not accounts:
            return None

        active_accounts = [a for a in accounts if a.get('status', 'A') == 'A']
        if not active_accounts:
            return None

        # Pick transaction type: 40% deposit, 30% withdrawal, 30% internal transfer
        tx_roll = self.rng.random()

        if tx_roll < 0.40:
            # Deposit (payroll/income)
            acct = self.rng.choice(active_accounts)
            amount = round(self.rng.uniform(profile['payroll_min'], profile['payroll_max']), 2)
            desc = self.rng.choice(profile['descriptions']['payroll'])
            return {
                'type': 'deposit', 'bank': bank,
                'account': acct['id'], 'amount': amount, 'description': desc,
            }

        elif tx_roll < 0.70:
            # Withdrawal (bill payment)
            acct = self.rng.choice(active_accounts)
            fresh = self._refresh_account(bank, acct['id'])
            if not fresh:
                return None
            amount = round(self.rng.uniform(profile['bill_min'], profile['bill_max']), 2)
            # Don't exceed balance (relaxed guards allow more organic NSF)
            guard_ceiling = 0.95 if self.relaxed_guards else 0.8
            guard_fallback = 0.6 if self.relaxed_guards else 0.3
            if amount > fresh['balance'] * guard_ceiling:
                amount = round(fresh['balance'] * guard_fallback, 2)
            if amount <= 0:
                return None
            desc = self.rng.choice(profile['descriptions']['bill'])
            return {
                'type': 'withdraw', 'bank': bank,
                'account': acct['id'], 'amount': amount, 'description': desc,
            }

        else:
            # Internal transfer (same-bank checking<->savings)
            if len(active_accounts) < 2:
                return None
            source = self.rng.choice(active_accounts)
            dest = self.rng.choice([a for a in active_accounts if a['id'] != source['id']])
            fresh = self._refresh_account(bank, source['id'])
            if not fresh:
                return None
            amount = round(self.rng.uniform(
                profile['internal_xfer_min'], profile['internal_xfer_max']), 2)
            xfer_ceiling = 0.85 if self.relaxed_guards else 0.5
            xfer_fallback = 0.4 if self.relaxed_guards else 0.2
            if amount > fresh['balance'] * xfer_ceiling:
                amount = round(fresh['balance'] * xfer_fallback, 2)
            if amount <= 0:
                return None
            desc = self.rng.choice(profile['descriptions']['xfer'])
            return {
                'type': 'transfer', 'bank': bank,
                'source_account': source['id'], 'dest_account': dest['id'],
                'amount': amount, 'description': desc,
            }

    def _execute_internal_transaction(self, tx: Dict, day_num: int,
                                      sim_time: datetime) -> Optional[str]:
        """Execute an internal transaction and return the status code."""
        bank = tx['bank']
        bridge = self.coordinator.nodes[bank]
        time_str = sim_time.strftime('%H:%M')

        if tx['type'] == 'deposit':
            result = bridge.process_transaction(
                tx['account'], 'D', tx['amount'], tx['description'])
            status = "OK" if result['status'] == '00' else f"FAIL{result['status']}"
            line = (f"  {time_str}  {bank}  DEP  {tx['account']}  "
                    f"${tx['amount']:>10,.2f}  {status}  {tx['description']}")

        elif tx['type'] == 'withdraw':
            result = bridge.process_transaction(
                tx['account'], 'W', tx['amount'], tx['description'])
            status = "OK" if result['status'] == '00' else f"FAIL{result['status']}"
            line = (f"  {time_str}  {bank}  WDR  {tx['account']}  "
                    f"${tx['amount']:>10,.2f}  {status}  {tx['description']}")

        elif tx['type'] == 'transfer':
            result = bridge.process_transaction(
                tx['source_account'], 'T', tx['amount'], tx['description'],
                target_id=tx['dest_account'])
            status = "OK" if result['status'] == '00' else f"FAIL{result['status']}"
            line = (f"  {time_str}  {bank}  XFR  {tx['source_account']}->{tx['dest_account']}  "
                    f"${tx['amount']:>10,.2f}  {status}  {tx['description']}")
        else:
            return None

        # Log to bank's internal log
        stream = f"{bank}_INTERNAL"
        self.logger.log(stream, line)
        self.logger.log_csv(stream, [
            day_num, sim_time.strftime('%Y-%m-%d'), time_str,
            tx['type'][0].upper(),
            bank, tx.get('account', tx.get('source_account', '')),
            bank, tx.get('account', tx.get('dest_account', '')),
            tx['amount'], result['status'], tx['description'], ''
        ])

        return result['status']

    # ── Monthly Batch Operations ──────────────────────────────────
    # Fees are assessed on the first business day of each month.
    # Interest is accrued on the last business day of each month.
    # These mirror real banking batch cycles.

    def _run_monthly_fees(self, day_num: int, sim_date: datetime):
        """Run fee assessment for all banks (day 1 of month)."""
        if not self.monthly_events:
            return

        print(f"  -- Monthly Fee Assessment (Day {day_num}) --")
        for bank in BANKS:
            bridge = self.coordinator.nodes[bank]
            result = bridge.run_fee_batch()
            fees = result.get('total_fees', 0.0)
            assessed = result.get('accounts_assessed', 0)
            self._monthly_fees[bank] += fees

            stream = f"{bank}_INTERNAL"
            self.logger.log(stream, f"  ** FEE BATCH: {assessed} accounts, ${fees:,.2f} collected")
            print(f"    {bank}: {assessed} assessed, ${fees:,.2f}")

    def _run_monthly_interest(self, day_num: int, sim_date: datetime):
        """Run interest accrual for all banks (last business day of month)."""
        if not self.monthly_events:
            return

        print(f"  -- Monthly Interest Accrual (Day {day_num}) --")
        for bank in BANKS:
            bridge = self.coordinator.nodes[bank]
            result = bridge.run_interest_batch()
            interest = result.get('total_interest', 0.0)
            processed = result.get('accounts_processed', 0)
            self._monthly_interest[bank] += interest

            stream = f"{bank}_INTERNAL"
            self.logger.log(stream, f"  ** INTEREST BATCH: {processed} accounts, ${interest:,.2f} accrued")
            print(f"    {bank}: {processed} processed, ${interest:,.2f}")

    def _run_reconciliation(self, day_num: int):
        """Run reconciliation for all banks."""
        print(f"\n  -- Reconciliation (Day {day_num}) --")
        all_match = True
        for bank in BANKS:
            bridge = self.coordinator.nodes[bank]
            result = bridge.run_reconciliation()
            matched = result.get('matched', 0)
            mismatched = result.get('mismatched', 0)
            status = "MATCH" if mismatched == 0 else "MISMATCH"
            if mismatched > 0:
                all_match = False

            stream = f"{bank}_INTERNAL"
            self.logger.log(stream, f"  ** RECONCILIATION: {matched} matched, {mismatched} mismatched — {status}")
            print(f"    {bank}: {matched} matched, {mismatched} mismatched — {status}")

        return all_match

    def _is_month_boundary(self, current_date: datetime, next_date: datetime) -> bool:
        """Check if we're crossing a month boundary."""
        return current_date.month != next_date.month

    def _is_first_business_day(self, sim_date: datetime) -> bool:
        """Check if this is the first business day of the month."""
        return sim_date.day <= 3 and sim_date.weekday() < 5

    def _is_last_business_day(self, sim_date: datetime) -> bool:
        """Check if this is the last business day of the month."""
        next_day = sim_date + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.month != sim_date.month

    def _check_month_transition(self, sim_date: datetime):
        """Handle month boundary: print monthly summaries and reset counters."""
        month_str = sim_date.strftime('%B %Y')
        if self._current_month is not None and self._current_month != month_str:
            # Print monthly summary for each bank
            for bank in BANKS:
                stream = f"{bank}_INTERNAL"
                self.logger.log_monthly_summary(
                    stream, self._current_month,
                    self._monthly_interest[bank], self._monthly_fees[bank],
                    self._monthly_internal_count[bank],
                    self._monthly_external_count[bank],
                )
            # Reset counters
            for bank in BANKS:
                self._monthly_interest[bank] = 0.0
                self._monthly_fees[bank] = 0.0
                self._monthly_internal_count[bank] = 0
                self._monthly_external_count[bank] = 0

        self._current_month = month_str

    # ── Scenario Event Handlers ───────────────────────────────────
    # Each handler executes a specific scripted event and logs it
    # prominently to both console and all log streams.

    def _log_event_banner(self, title: str, day_num: int, detail_lines: List[str]):
        """Print a distinct event banner to console and all log streams."""
        banner = f"\n  !! EVENT: {title} — Day {day_num}"
        print(banner)
        for line in detail_lines:
            print(f"     {line}")
        print()

        # Log to all streams
        for bank in BANKS:
            stream = f"{bank}_INTERNAL"
            self.logger.log(stream, banner)
            for line in detail_lines:
                self.logger.log(stream, f"     {line}")
        self.logger.log('SETTLEMENT', banner)
        for line in detail_lines:
            self.logger.log('SETTLEMENT', f"     {line}")

    def _event_freeze_account(self, event: SimulationEvent, day_num: int):
        """Freeze an account -- subsequent transactions will fail with status 04."""
        bank = event.params['bank']
        account = event.params['account']
        bridge = self.coordinator.nodes[bank]
        result = bridge.update_account_status(account, 'F')

        self._log_event_banner("REGULATORY FREEZE", day_num, [
            f"{bank} / {account}: Suspicious activity flagged by compliance",
            f"All subsequent operations on this account will fail (status 04)",
            f"Result: {result['message']}",
        ])
        self._load_accounts()

    def _event_close_account(self, event: SimulationEvent, day_num: int):
        """Close an account -- future transactions to it will fail."""
        bank = event.params['bank']
        account = event.params['account']
        bridge = self.coordinator.nodes[bank]
        result = bridge.update_account_status(account, 'C')

        self._log_event_banner("ACCOUNT CLOSURE", day_num, [
            f"{bank} / {account}: Account closed per customer request",
            f"Future transactions to this account will be rejected",
            f"Result: {result['message']}",
        ])
        self._load_accounts()

    def _event_tamper_balance(self, event: SimulationEvent, day_num: int):
        """Directly edit a DAT file balance -- bypasses integrity chain.

        This is the key demo moment: the tamper modifies the COBOL data file
        without going through the bridge. The integrity verification system
        will detect this discrepancy on its next run.
        """
        bank = event.params['bank']
        account = event.params['account']
        amount = event.params['amount']

        tamper_balance(self.data_dir, bank, account, amount)

        self._log_event_banner("BALANCE TAMPER (EXTERNAL ATTACK)", day_num, [
            f"{bank} / {account}: Balance set to ${amount:,.2f} via direct DAT edit",
            f"This bypasses the integrity chain — verification WILL detect it",
            f"The COBOL ledger has been compromised. Can the system catch it?",
        ])
        # Do NOT reload accounts -- tamper is in DAT only, DB still has real value

    def _event_large_transfer(self, event: SimulationEvent, day_num: int):
        """Attempt a transfer exceeding daily limits."""
        p = event.params
        self._log_event_banner("LARGE TRANSFER ATTEMPTED", day_num, [
            f"{p['source_bank']} / {p['source_account']} -> {p['dest_bank']} / {p['dest_account']}",
            f"Amount: ${p['amount']:,.2f} — exceeds $50,000 daily wire limit",
        ])

        result = self.coordinator.execute_transfer(
            source_bank=p['source_bank'], source_account=p['source_account'],
            dest_bank=p['dest_bank'], dest_account=p['dest_account'],
            amount=p['amount'], description="Large wire transfer attempt",
        )

        status = result.status
        error = result.error or "none"
        status_line = f"Result: {status} — {error}"
        if status != "COMPLETED":
            status_line = f"BLOCKED — {status}: {error}"
            self.total_failed += 1
        else:
            self.total_completed += 1
            self.total_volume += p['amount']

        print(f"     {status_line}")
        self.logger.log('SETTLEMENT', f"     {status_line}")

    def _event_drain_transfers(self, event: SimulationEvent, day_num: int):
        """Multiple transfers from a low-balance account -- expect NSF cascade."""
        bank = event.params['bank']
        source = event.params['account']
        dest = event.params['dest_account']
        count = event.params['count']
        amount = event.params['amount']
        bridge = self.coordinator.nodes[bank]

        self._log_event_banner("DRAIN TRANSFERS", day_num, [
            f"{bank} / {source}: {count} transfers of ${amount:,.2f} each",
            f"Low-balance account — expecting NSF cascade after initial success(es)",
        ])

        for i in range(count):
            result = bridge.process_transaction(
                source, 'T', amount, f"Drain transfer {i+1}/{count}", target_id=dest)
            status = "OK" if result['status'] == '00' else f"FAIL{result['status']}"
            bal = result.get('new_balance', '?')
            line = f"     Transfer {i+1}/{count}: ${amount:,.2f}  {status}  (balance: ${bal})"
            print(line)

            stream = f"{bank}_INTERNAL"
            self.logger.log(stream, line)

            if result['status'] == '00':
                self.total_completed += 1
                self.total_volume += amount
            else:
                self.total_failed += 1

        self._load_accounts()

    def _event_suspicious_burst(self, event: SimulationEvent, day_num: int):
        """Multiple near-CTR deposits -- structuring pattern.

        Deposits just below the $10,000 Currency Transaction Report threshold.
        In real banking, this pattern ("structuring") is a federal crime.
        """
        bank = event.params['bank']
        account = event.params['account']
        count = event.params['count']
        min_amt = event.params['min_amount']
        max_amt = event.params['max_amount']
        bridge = self.coordinator.nodes[bank]

        self._log_event_banner("SUSPICIOUS DEPOSIT BURST", day_num, [
            f"{bank} / {account}: {count} deposits between ${min_amt:,.2f}-${max_amt:,.2f}",
            f"Pattern: Just below $10,000 CTR threshold — possible structuring",
        ])

        for i in range(count):
            amount = round(self.rng.uniform(min_amt, max_amt), 2)
            result = bridge.process_transaction(
                account, 'D', amount, f"Cash deposit #{i+1}")
            status = "OK" if result['status'] == '00' else f"FAIL{result['status']}"
            line = f"     Deposit {i+1}/{count}: ${amount:,.2f}  {status}"
            print(line)

            stream = f"{bank}_INTERNAL"
            self.logger.log(stream, line)

            if result['status'] == '00':
                self.total_completed += 1
                self.total_volume += amount
            else:
                self.total_failed += 1

        self._load_accounts()

    def _execute_day_events(self, day_num: int, sim_date: datetime):
        """Fire any scenario events scheduled for this day."""
        if not self.director:
            return

        events = self.director.get_events_for_day(day_num)
        if not events:
            return

        handlers = {
            EventType.FREEZE_ACCOUNT: self._event_freeze_account,
            EventType.CLOSE_ACCOUNT: self._event_close_account,
            EventType.TAMPER_BALANCE: self._event_tamper_balance,
            EventType.LARGE_TRANSFER: self._event_large_transfer,
            EventType.DRAIN_TRANSFERS: self._event_drain_transfers,
            EventType.SUSPICIOUS_BURST: self._event_suspicious_burst,
        }

        for event in events:
            handler = handlers.get(event.event_type)
            if handler:
                handler(event, day_num)
                event.fired = True

    # ── Daily Simulation Loop ─────────────────────────────────────
    # Each simulated day generates a random number of transactions
    # distributed across banking hours (8am-6pm). The mix of internal
    # vs external is controlled by internal_ratio.

    def _run_day(self, day_num: int, sim_date: datetime):
        """Execute one simulated banking day."""
        # Refresh account cache to pick up balance changes from prior days
        self._load_accounts()

        date_str = sim_date.strftime('%a %Y-%m-%d')
        header = f"\n{'=' * 3} DAY {day_num} | {date_str} {'=' * (52 - len(date_str) - len(str(day_num)))}"
        print(header)

        # Check month transition
        self._check_month_transition(sim_date)

        # Monthly events -- use month key to avoid double-firing
        month_key = sim_date.strftime('%Y-%m')
        if self._is_first_business_day(sim_date) and month_key not in self._fees_run_months:
            self._run_monthly_fees(day_num, sim_date)
            self._fees_run_months.add(month_key)

        if self._is_last_business_day(sim_date) and month_key not in self._interest_run_months:
            self._run_monthly_interest(day_num, sim_date)
            self._interest_run_months.add(month_key)

        # Log day header to all streams
        self.logger.log_day_header('SETTLEMENT', day_num, date_str)
        for bank in BANKS:
            self.logger.log_day_header(f'{bank}_INTERNAL', day_num, date_str)

        # Fire scenario events BEFORE random transactions
        if self.scenarios:
            self._execute_day_events(day_num, sim_date)

        # Generate transaction count for the day
        tx_count = self.rng.randint(self.tx_min, self.tx_max)

        # Split between internal and external
        internal_count = int(tx_count * self.internal_ratio / 100)
        external_count = tx_count - internal_count

        # Distribute across banking hours (8am-6pm = 10 hours)
        banking_minutes = 10 * 60
        all_tx_times = sorted([self.rng.randint(0, banking_minutes - 1) for _ in range(tx_count)])

        day_completed = 0
        day_failed = 0
        day_volume = 0.0
        internal_done = 0
        external_done = 0

        for i, minutes_offset in enumerate(all_tx_times):
            if self._stopped:
                break

            sim_time = sim_date.replace(hour=8, minute=0, second=0) + timedelta(minutes=minutes_offset)
            time_str = sim_time.strftime('%H:%M')

            # ── Time Scaling ──────────────────────────────────────
            # Sleep proportional to the gap between consecutive transactions.
            # At time_scale=3600, a 1-minute gap in sim time = 1/60 second real time.
            # At time_scale=0, no sleeping at all (maximum speed).
            if self.time_scale > 0 and i > 0:
                prev_minutes = all_tx_times[i - 1]
                gap_sim_seconds = (minutes_offset - prev_minutes) * 60
                gap_real_seconds = gap_sim_seconds / self.time_scale
                if gap_real_seconds > 0.01:
                    time.sleep(gap_real_seconds)

            # Decide: internal or external
            is_internal = internal_done < internal_count and (
                external_done >= external_count or self.rng.random() < self.internal_ratio / 100
            )

            if is_internal:
                # Pick a random bank for internal activity
                bank = self.rng.choice(BANKS)
                tx = self._pick_internal_transaction(bank)
                if tx:
                    status = self._execute_internal_transaction(tx, day_num, sim_time)
                    if status == '00':
                        day_completed += 1
                        day_volume += tx['amount']
                        self._monthly_internal_count[bank] += 1
                    else:
                        day_failed += 1
                    internal_done += 1
                    self.total_internal += 1

                    # Print compact line to console
                    tx_type = tx['type'][:3].upper()
                    acct = tx.get('account', tx.get('source_account', ''))
                    status_display = "OK" if status == '00' else f"FAIL"
                    print(f"  {time_str}  {bank}  {tx_type}  {acct}  "
                          f"${tx['amount']:>10,.2f}  {status_display}")
                else:
                    internal_done += 1
            else:
                # External transfer -- goes through settlement coordinator
                transfer = self._pick_external_transfer()
                if not transfer:
                    external_done += 1
                    continue

                result = self.coordinator.execute_transfer(**transfer, sim_date=sim_date)

                ref = result.settlement_ref
                src = f"{transfer['source_bank']}:{transfer['source_account']}"
                dst = f"{transfer['dest_bank']}:{transfer['dest_account']}"
                amt = f"${transfer['amount']:,.2f}"

                if result.status == "COMPLETED":
                    status = "OK"
                    day_completed += 1
                    day_volume += transfer['amount']
                    self._monthly_external_count[transfer['source_bank']] += 1
                else:
                    error_short = result.error.split(':')[-1].strip()[:12] if result.error else "ERROR"
                    status = f"FAIL {error_short}"
                    day_failed += 1

                print(f"  {time_str}  {ref}  {src} -> {dst}  {amt:>12}  {status}")

                # Log to settlement log
                self.logger.log('SETTLEMENT',
                    f"  {time_str}  {ref}  {src} -> {dst}  {amt:>12}  {status}")
                self.logger.log_csv('SETTLEMENT', [
                    day_num, sim_date.strftime('%Y-%m-%d'), time_str, 'S',
                    transfer['source_bank'], transfer['source_account'],
                    transfer['dest_bank'], transfer['dest_account'],
                    transfer['amount'], result.status, transfer['description'], ref
                ])

                external_done += 1
                self.total_external += 1

        # EOD summary
        self.total_completed += day_completed
        self.total_failed += day_failed
        self.total_volume += day_volume
        self.days_run += 1

        summary_line = f"  {day_completed} completed | {day_failed} failed | ${day_volume:,.2f} volume"
        print(f"  -- EOD Summary {'-' * 50}")
        print(summary_line)

        # Log EOD to all streams
        # SETTLEMENT stream only counts external (inter-bank) transactions
        self.logger.log_eod_summary('SETTLEMENT', external_done,
                                     day_failed, day_volume)
        for bank in BANKS:
            self.logger.log_eod_summary(f'{bank}_INTERNAL', day_completed, day_failed, day_volume)

        # Flush logs to disk after each day
        self.logger.flush()

    # ── Integrity Verification ────────────────────────────────────
    # Periodic verification runs during simulation to demonstrate the
    # system catching anomalies in real-time (especially the tamper event).

    def _run_verification(self, day_num: int):
        """Run cross-node integrity verification."""
        print(f"\n  -- Integrity Verification (Day {day_num}) --")
        verifier = CrossNodeVerifier(data_dir=self.data_dir)
        report = verifier.verify_all()
        verifier.close()

        chains_ok = "OK" if report.all_chains_intact else "BROKEN"
        settlements_ok = "OK" if report.all_settlements_matched else "MISMATCH"
        print(f"  Chains: {chains_ok}  Settlements: {settlements_ok} "
              f"({report.settlements_checked} checked, {report.verification_time_ms:.0f}ms)")

        # Check if a tamper event has fired -- produce dramatic output
        tamper_params = self.director.get_tamper_params() if self.director else None
        if tamper_params and report.balance_drift:
            tamper_bank = tamper_params['bank']
            tamper_acct = tamper_params['account']
            tamper_amt = tamper_params['amount']
            has_drift = any(
                tamper_acct in issue
                for issues in report.balance_drift.values()
                for issue in issues
            )
            if has_drift:
                print()
                print(f"  ╔══════════════════════════════════════════════════════╗")
                print(f"  ║  !! TAMPER DETECTED — {tamper_bank}                      ║")
                print(f"  ╠══════════════════════════════════════════════════════╣")
                print(f"  ║  Account: {tamper_acct}                              ║")
                print(f"  ║  DAT file balance: ${tamper_amt:>12,.2f}  (FORGED)    ║")
                print(f"  ║  DB ledger balance: differs  (AUTHENTIC)             ║")
                print(f"  ║                                                      ║")
                print(f"  ║  The integrity layer caught what COBOL alone could   ║")
                print(f"  ║  not. The DAT file was modified outside the chain.   ║")
                print(f"  ╚══════════════════════════════════════════════════════╝")
                print()

                # Log the tamper detection
                for bank in BANKS:
                    self.logger.log(f"{bank}_INTERNAL",
                        f"  !! TAMPER DETECTED on {tamper_bank}/{tamper_acct} — "
                        f"DAT=${tamper_amt:,.2f} vs DB ledger")
                self.logger.log('SETTLEMENT',
                    f"  !! TAMPER DETECTED on {tamper_bank}/{tamper_acct}")
                return

        if report.anomalies:
            for a in report.anomalies[:5]:
                if 'balance' in a.lower() or 'drift' in a.lower() or 'mismatch' in a.lower():
                    print(f"  ~ {a[:70]} (expected — internal activity)")
                else:
                    print(f"  ! {a[:70]}")

    def _print_final_summary(self):
        """Print final simulation summary."""
        print(f"\n{'=' * 66}")
        print(f"  SIMULATION COMPLETE")
        print(f"  {self.days_run} days | {self.total_completed} completed | "
              f"{self.total_failed} failed | ${self.total_volume:,.2f} total volume")
        print(f"  Internal: {self.total_internal} | External: {self.total_external}")
        if self.output_dir:
            print(f"  Logs: {self.output_dir}/")
        print(f"{'=' * 66}")

    # ── Main Run Loop ─────────────────────────────────────────────
    # The outer simulation loop advances day-by-day, skipping weekends,
    # running scenario events, and periodically verifying integrity.

    def run(self, days: Optional[int] = None):
        """
        Run the simulation.

        Args:
            days: Number of days to simulate, or None for continuous mode.
        """
        # Load account data
        self._load_accounts()

        # Initialize scenario director
        if self.scenarios and days is not None:
            self.director = ScenarioDirector(total_days=days)
            event_count = len(self.director.events)
            print(f"  Scenarios: ON ({event_count} events scheduled)")
            for e in self.director.events:
                print(f"    Day {e.day:>3}: {e.event_type:<20} — {e.description[:50]}")
            print()
        elif self.scenarios:
            # Continuous mode -- use 365-day schedule
            self.director = ScenarioDirector(total_days=365)

        # Set up graceful shutdown (Ctrl+C finishes current day, then stops)
        original_sigint = signal.getsignal(signal.SIGINT)

        def handle_sigint(signum, frame):
            self._stopped = True
            print("\n\n  Ctrl+C received -- finishing current day...")

        signal.signal(signal.SIGINT, handle_sigint)

        sim_date = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        day_num = 0

        try:
            while not self._stopped:
                day_num += 1
                if days is not None and day_num > days:
                    break

                self._run_day(day_num, sim_date)

                # Periodic verification
                if self.verify_every > 0 and day_num % self.verify_every == 0:
                    self._run_verification(day_num)

                # Periodic reconciliation (every 30 days)
                if day_num % 30 == 0:
                    self._run_reconciliation(day_num)

                sim_date += timedelta(days=1)
                # Skip weekends (banks don't operate on Sat/Sun)
                while sim_date.weekday() >= 5:
                    sim_date += timedelta(days=1)

        finally:
            signal.signal(signal.SIGINT, original_sigint)
            self._print_final_summary()
            self.logger.close()
