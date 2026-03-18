# Security Policy

## Scope

This is an **educational demo project** — a COBOL teaching resource, not production banking software. It processes no real financial data and holds no real customer information.

The security scope covers:

- **The codebase** in this repository
- **The hosted demo** at [cobol-legacy-ledger-production.up.railway.app](https://cobol-legacy-ledger-production.up.railway.app/console/)

## Reporting a Vulnerability

If you discover a security issue, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Use [GitHub private vulnerability reporting](https://github.com/albertdobmeyer/cobol-legacy-ledger/security/advisories/new) to submit your report.
3. Include steps to reproduce, affected components, and potential impact.

You should receive an acknowledgment within 72 hours.

## What Qualifies

- XSS, injection, or path traversal in the web console or API
- Authentication/authorization bypasses in the RBAC layer
- Secrets or credentials accidentally committed to the repository
- Dependency vulnerabilities with a viable exploit path

## What Does Not Qualify

- The intentional tamper demo (this is a feature, not a bug)
- Missing HTTPS/TLS in local development
- Denial-of-service against the free-tier Railway deployment
- Issues in GnuCOBOL or third-party dependencies without a project-specific exploit
