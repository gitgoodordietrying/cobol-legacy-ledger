# Scripts

## Primary (used by Makefile)

| Script | `make` target | Purpose |
|--------|---------------|---------|
| `build.sh` | `make build` | Compile all COBOL programs (`cobc`); Docker fallback if not installed |
| `seed.sh` | `make seed` | Seed all 6 nodes with demo accounts and batch transactions |
| `prove.sh` | `make prove` | Full end-to-end proof: compile → seed → settle → verify → tamper → detect |
| `checkpoint.sh` | `make checkpoint-save/restore` | Save/restore data snapshots for classroom lessons |

## Helpers

| Script | Purpose |
|--------|---------|
| `cobol-run.sh` | Docker wrapper — builds image if missing, runs command in container |
| `cobol-test.sh` | COBOL-only test harness (compile + run SMOKETEST) |
| `cobol-test-suite.sh` | Extended COBOL test suite (all 10 programs) |
| `demo.sh` | Interactive demo script for presentations |
| `run-simulation.sh` | Start a simulation from the command line |
| `run_smoke_test.sh` | Quick smoke test (compile + verify output) |
| `setup.sh` | First-time environment setup (venv + deps) |
| `install_gnucobol.sh` | Install GnuCOBOL on Linux/macOS |
| `install_gnucobol.ps1` | Install GnuCOBOL on Windows (Chocolatey) |

## Data Generators

| Script | Purpose |
|--------|---------|
| `create_accounts_dat.py` | Generate ACCOUNTS.DAT files (95-byte fixed-width records) |
| `gen_employees.py` | Generate EMPLOYEES.DAT for the payroll sidecar |
| `seed_docker.py` | Seed nodes inside the Docker container |
| `capture_screenshots.py` | Playwright screenshot capture for documentation |
| `validate_balance_parser.py` | Verify balance parsing matches COBOL PIC 9(10)V99 format |
