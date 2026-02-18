# GnuCOBOL Installation Helper for Windows
# This script attempts to install GnuCOBOL using available package managers

param(
    [switch]$UseWSL,
    [switch]$SkipCheck
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "GnuCOBOL Installation Helper" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if already installed
if (-not $SkipCheck) {
    Write-Host "Checking if GnuCOBOL is already installed..." -ForegroundColor Yellow
    $cobcPath = Get-Command cobc -ErrorAction SilentlyContinue
    if ($cobcPath) {
        Write-Host "[SUCCESS] GnuCOBOL is already installed!" -ForegroundColor Green
        Write-Host "Location: $($cobcPath.Source)" -ForegroundColor Gray
        Write-Host "Version: $(cobc --version 2>&1)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "You can now run: ./scripts/run_smoke_test.sh" -ForegroundColor Green
        exit 0
    }
    Write-Host "[INFO] GnuCOBOL not found. Proceeding with installation..." -ForegroundColor Yellow
    Write-Host ""
}

# Option 1: WSL Installation (Recommended for Windows)
if ($UseWSL -or (Get-Command wsl -ErrorAction SilentlyContinue)) {
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Option 1: Installing via WSL (Recommended)" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Check if WSL is installed
    $wslInstalled = Get-Command wsl -ErrorAction SilentlyContinue
    if (-not $wslInstalled) {
        Write-Host "[INFO] WSL is not installed. Would you like to install it?" -ForegroundColor Yellow
        Write-Host "This requires administrator privileges and will install Ubuntu." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To install WSL manually:" -ForegroundColor Cyan
        Write-Host "  1. Open PowerShell as Administrator" -ForegroundColor Gray
        Write-Host "  2. Run: wsl --install" -ForegroundColor Gray
        Write-Host "  3. Restart your computer" -ForegroundColor Gray
        Write-Host "  4. After restart, run this script again" -ForegroundColor Gray
        Write-Host ""
    } else {
        Write-Host "[INFO] WSL detected. Installing GnuCOBOL in your default WSL distro..." -ForegroundColor Yellow
        Write-Host ""

        try {
            Write-Host "Running: wsl sudo apt-get update ..." -ForegroundColor Gray
            wsl sudo apt-get update

            Write-Host "Running: wsl sudo apt-get install -y gnucobol ..." -ForegroundColor Gray
            wsl sudo apt-get install -y gnucobol

            $version = wsl cobc --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host ""
                Write-Host "[SUCCESS] GnuCOBOL installed in WSL!" -ForegroundColor Green
                Write-Host "Version: $version" -ForegroundColor Gray
                Write-Host ""
                Write-Host "Run the smoke test from PowerShell (from this project folder):" -ForegroundColor Cyan
                Write-Host "  wsl bash ./scripts/run_smoke_test.sh" -ForegroundColor Gray
                Write-Host ""
                Write-Host "Or open WSL (wsl), cd to this project, then run:" -ForegroundColor Cyan
                Write-Host "  ./scripts/run_smoke_test.sh" -ForegroundColor Gray
                exit 0
            }
        } catch {
            # fall through to manual instructions
        }

        Write-Host "[WARNING] Could not verify GnuCOBOL in WSL." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Install manually inside WSL:" -ForegroundColor Cyan
        Write-Host "  wsl" -ForegroundColor Gray
        Write-Host "  sudo apt-get update && sudo apt-get install -y gnucobol" -ForegroundColor Gray
        Write-Host "  cobc --version" -ForegroundColor Gray
        Write-Host ""
    }
}

# Option 2: Chocolatey
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Option 2: Installing via Chocolatey" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$chocoInstalled = Get-Command choco -ErrorAction SilentlyContinue
if ($chocoInstalled) {
    Write-Host "[INFO] Chocolatey detected. Installing GnuCOBOL..." -ForegroundColor Yellow
    
    try {
        # Run as administrator if needed
        choco install gnucobol -y
        
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        
        Write-Host ""
        Write-Host "[SUCCESS] GnuCOBOL installed via Chocolatey!" -ForegroundColor Green
        
        # Verify installation
        $cobcPath = Get-Command cobc -ErrorAction SilentlyContinue
        if ($cobcPath) {
            Write-Host "Location: $($cobcPath.Source)" -ForegroundColor Gray
            Write-Host "Version: $(cobc --version 2>&1)" -ForegroundColor Gray
            Write-Host ""
            Write-Host "You can now run: ./scripts/run_smoke_test.sh" -ForegroundColor Green
            exit 0
        } else {
            Write-Host "[WARNING] Installation completed but 'cobc' not found in PATH." -ForegroundColor Yellow
            Write-Host "You may need to restart your terminal or add GnuCOBOL to PATH manually." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[ERROR] Chocolatey installation failed: $_" -ForegroundColor Red
        Write-Host ""
    }
} else {
    Write-Host "[INFO] Chocolatey not found." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To install Chocolatey:" -ForegroundColor Cyan
    Write-Host "  1. Open PowerShell as Administrator" -ForegroundColor Gray
    Write-Host "  2. Run: Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))" -ForegroundColor Gray
    Write-Host "  3. Then run this script again" -ForegroundColor Gray
    Write-Host ""
}

# Option 3: Winget (Windows Package Manager)
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Option 3: Installing via Winget" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$wingetInstalled = Get-Command winget -ErrorAction SilentlyContinue
if ($wingetInstalled) {
    Write-Host "[INFO] Winget detected. Checking for GnuCOBOL package..." -ForegroundColor Yellow
    
    try {
        # Check if package exists
        $packageInfo = winget search gnucobol 2>&1
        if ($packageInfo -match "gnucobol") {
            Write-Host "[INFO] Installing GnuCOBOL via Winget..." -ForegroundColor Yellow
            winget install --id=GnuCOBOL.GnuCOBOL -e --accept-package-agreements --accept-source-agreements
            
            # Refresh PATH
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
            
            Write-Host ""
            Write-Host "[SUCCESS] GnuCOBOL installed via Winget!" -ForegroundColor Green
            
            # Verify installation
            $cobcPath = Get-Command cobc -ErrorAction SilentlyContinue
            if ($cobcPath) {
                Write-Host "Location: $($cobcPath.Source)" -ForegroundColor Gray
                Write-Host "Version: $(cobc --version 2>&1)" -ForegroundColor Gray
                Write-Host ""
                Write-Host "You can now run: ./scripts/run_smoke_test.sh" -ForegroundColor Green
                exit 0
            } else {
                Write-Host "[WARNING] Installation completed but 'cobc' not found in PATH." -ForegroundColor Yellow
                Write-Host "You may need to restart your terminal or add GnuCOBOL to PATH manually." -ForegroundColor Yellow
            }
        } else {
            Write-Host "[INFO] GnuCOBOL package not found in Winget repository." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[ERROR] Winget installation failed: $_" -ForegroundColor Red
        Write-Host ""
    }
} else {
    Write-Host "[INFO] Winget not found (requires Windows 10 1809+ or Windows 11)." -ForegroundColor Yellow
    Write-Host ""
}

# Option 4: Manual Installation Instructions
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Option 4: Manual Installation" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "If automated installation didn't work, you can install manually:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Method A: WSL (Recommended)" -ForegroundColor Cyan
Write-Host "  1. Open PowerShell as Administrator" -ForegroundColor Gray
Write-Host "  2. Run: wsl --install" -ForegroundColor Gray
Write-Host "  3. Restart your computer" -ForegroundColor Gray
Write-Host "  4. Open Ubuntu from Start Menu" -ForegroundColor Gray
Write-Host "  5. Run: sudo apt-get update && sudo apt-get install -y gnucobol" -ForegroundColor Gray
Write-Host "  6. Verify: cobc --version" -ForegroundColor Gray
Write-Host "  7. Run scripts from WSL: wsl bash ./scripts/run_smoke_test.sh" -ForegroundColor Gray
Write-Host ""

Write-Host "Method B: Download Pre-built Binary" -ForegroundColor Cyan
Write-Host "  1. Visit: https://gnucobol.sourceforge.io/" -ForegroundColor Gray
Write-Host "  2. Download Windows binary distribution" -ForegroundColor Gray
Write-Host "  3. Extract to a directory (e.g., C:\gnucobol)" -ForegroundColor Gray
Write-Host "  4. Add to PATH: C:\gnucobol\bin" -ForegroundColor Gray
Write-Host "     - Open System Properties > Environment Variables" -ForegroundColor Gray
Write-Host "     - Edit PATH variable, add: C:\gnucobol\bin" -ForegroundColor Gray
Write-Host "  5. Restart terminal and verify: cobc --version" -ForegroundColor Gray
Write-Host ""

Write-Host "Method C: Chocolatey (if you install Chocolatey first)" -ForegroundColor Cyan
Write-Host "  1. Install Chocolatey (see instructions above)" -ForegroundColor Gray
Write-Host "  2. Run: choco install gnucobol -y" -ForegroundColor Gray
Write-Host "  3. Restart terminal and verify: cobc --version" -ForegroundColor Gray
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "After Installation" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Once GnuCOBOL is installed, verify it works:" -ForegroundColor Yellow
Write-Host "  cobc --version" -ForegroundColor Gray
Write-Host ""
Write-Host "Then run the smoke test:" -ForegroundColor Yellow
Write-Host "  ./scripts/run_smoke_test.sh" -ForegroundColor Gray
Write-Host ""
Write-Host "Or if using WSL:" -ForegroundColor Yellow
Write-Host "  wsl bash ./scripts/run_smoke_test.sh" -ForegroundColor Gray
Write-Host ""
