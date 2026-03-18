# Contributing to COBOL Legacy Ledger

Thank you for your interest in contributing! This project is an educational COBOL teaching resource.

## Getting Started

```bash
# Clone and install
git clone https://github.com/albertdobmeyer/cobol-legacy-ledger.git
cd cobol-legacy-ledger
pip install -e ".[dev]"

# Build COBOL (optional — Python fallback works without it)
./scripts/build.sh

# Seed demo data
./scripts/seed.sh

# Run tests
python -m pytest python/tests/ -v --ignore=python/tests/test_e2e_playwright.py

# Start dev server
uvicorn python.api.app:app --reload
```

## Key Principles

1. **COBOL Immutability** — Never modify the COBOL programs. Wrap them with Python observation instead.
2. **Educational Comments** — Every source file teaches concepts inline. New code should follow the same standard.
3. **Test Everything** — Every feature must have tests. Current count: 800+ tests.
4. **No Node.js** — The web console is static HTML/CSS/JS served via FastAPI. No npm, no build process.

## Code Style

- **Python**: Follow existing patterns — module docstrings (20-40 lines), section banners (`# -- Title ---`), class/method docstrings
- **COBOL**: Follow existing patterns — IDENTIFICATION DIVISION headers, `COBOL CONCEPT:` comment blocks, KNOWN_ISSUES.md entries for intentional bugs
- **JavaScript**: Vanilla JS, no frameworks, modular files

## Reporting Issues

- Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) for bugs
- Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md) for new ideas
- Include your Python version, OS, and whether GnuCOBOL is installed

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes with tests
4. Ensure all tests pass: `python -m pytest python/tests/ -v --ignore=python/tests/test_e2e_playwright.py`
5. Submit a PR with a clear description of what changed and why
