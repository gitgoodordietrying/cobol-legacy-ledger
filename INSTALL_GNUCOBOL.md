# GnuCOBOL Installation Guide

**Quick Answer**: You can install GnuCOBOL automatically using the helper scripts, or manually using package managers.

---

## Automated Installation (Recommended)

### Windows (PowerShell)
```powershell
.\scripts\install_gnucobol.ps1
```

This script will:
1. Check if GnuCOBOL is already installed
2. Try to install via Chocolatey (if available)
3. Try to install via Winget (if available)
4. Provide instructions for WSL installation
5. Provide manual installation instructions if automated methods fail

### Linux/macOS/WSL (Bash)
```bash
./scripts/install_gnucobol.sh
```

This script will:
1. Check if GnuCOBOL is already installed
2. Detect your OS and use the appropriate package manager:
   - **Debian/Ubuntu**: `apt-get`
   - **RHEL/CentOS**: `yum`
   - **Fedora**: `dnf`
   - **Arch Linux**: `pacman`
   - **macOS**: `brew`

---

## Manual Installation Options

### Option 1: WSL (Windows Subsystem for Linux) — **Recommended for Windows**

**Why WSL?** GnuCOBOL works best on Linux. WSL gives you a Linux environment on Windows.

1. **Install WSL** (if not already installed):
   ```powershell
   # Open PowerShell as Administrator
   wsl --install
   ```
   Restart your computer when prompted.

2. **Open Ubuntu** from Start Menu and run:
   ```bash
   sudo apt-get update
   sudo apt-get install -y gnucobol
   cobc --version
   ```

3. **Run scripts from WSL**:
   ```bash
   # Navigate to your project in WSL
   cd /mnt/b/Projects/portfolio/cobol-legacy-ledger
   
   # Run the smoke test
   bash ./scripts/run_smoke_test.sh
   ```

**Note**: Your Windows files are accessible in WSL at `/mnt/c/...` or `/mnt/b/...` etc.

---

### Option 2: Chocolatey (Windows Package Manager)

1. **Install Chocolatey** (if not already installed):
   ```powershell
   # Open PowerShell as Administrator
   Set-ExecutionPolicy Bypass -Scope Process -Force
   [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
   iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
   ```

2. **Install GnuCOBOL**:
   ```powershell
   choco install gnucobol -y
   ```

3. **Restart your terminal** and verify:
   ```powershell
   cobc --version
   ```

---

### Option 3: Winget (Windows Package Manager)

**Note**: Winget requires Windows 10 1809+ or Windows 11.

```powershell
winget install --id=GnuCOBOL.GnuCOBOL -e --accept-package-agreements --accept-source-agreements
```

Restart your terminal and verify:
```powershell
cobc --version
```

---

### Option 4: Download Pre-built Binary (Windows)

1. Visit: https://gnucobol.sourceforge.io/
2. Download Windows binary distribution
3. Extract to a directory (e.g., `C:\gnucobol`)
4. Add to PATH:
   - Open **System Properties** > **Environment Variables**
   - Edit **PATH** variable
   - Add: `C:\gnucobol\bin`
5. Restart terminal and verify:
   ```powershell
   cobc --version
   ```

---

### Option 5: Linux (Debian/Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y gnucobol
cobc --version
```

---

### Option 6: macOS

```bash
brew install gnu-cobol
cobc --version
```

---

## Verify Installation

After installation, verify it works:

```bash
# Check version
cobc --version

# Should output something like:
# cobc (GnuCOBOL) 3.2.0
# Copyright (C) 2020 Free Software Foundation, Inc.
```

---

## Run Smoke Test

Once GnuCOBOL is installed, run the smoke test:

```bash
# Linux/macOS/WSL
./scripts/run_smoke_test.sh

# Windows (if installed natively)
bash ./scripts/run_smoke_test.sh

# Windows (WSL)
wsl bash ./scripts/run_smoke_test.sh
```

---

## Troubleshooting

### "cobc: command not found"
- **Windows**: Restart your terminal after installation
- **Linux/macOS**: Make sure GnuCOBOL is in your PATH
- **WSL**: Make sure you're running commands inside WSL, not PowerShell

### "Permission denied" (Linux/macOS)
- Use `sudo` for installation commands
- Make sure you have administrator privileges

### Installation fails
- Try the manual installation method for your OS
- Check the [GnuCOBOL website](https://gnucobol.sourceforge.io/) for platform-specific instructions
- Consider using WSL (Option 1) as it's the most reliable on Windows

---

## Recommended Approach

**For Windows users**: Use **WSL** (Option 1). It's the most reliable and matches the Linux environment where GnuCOBOL is primarily developed and tested.

**For Linux/macOS users**: Use the automated script (`./scripts/install_gnucobol.sh`) or your system's package manager.

---

*Last updated: 2026-02-18*
