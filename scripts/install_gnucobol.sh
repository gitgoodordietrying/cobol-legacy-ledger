#!/bin/bash
# GnuCOBOL Installation Helper for Linux/macOS/WSL
# This script installs GnuCOBOL using the appropriate package manager

set -e

echo "=========================================="
echo "GnuCOBOL Installation Helper"
echo "=========================================="
echo ""

# Check if already installed
if command -v cobc &> /dev/null; then
    echo "[SUCCESS] GnuCOBOL is already installed!"
    echo "Version: $(cobc --version)"
    echo ""
    echo "You can now run: ./scripts/run_smoke_test.sh"
    exit 0
fi

echo "[INFO] GnuCOBOL not found. Proceeding with installation..."
echo ""

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v apt-get &> /dev/null; then
        echo "[INFO] Detected Debian/Ubuntu. Installing via apt-get..."
        sudo apt-get update
        sudo apt-get install -y gnucobol
    elif command -v yum &> /dev/null; then
        echo "[INFO] Detected RHEL/CentOS. Installing via yum..."
        sudo yum install -y gnucobol
    elif command -v dnf &> /dev/null; then
        echo "[INFO] Detected Fedora. Installing via dnf..."
        sudo dnf install -y gnucobol
    elif command -v pacman &> /dev/null; then
        echo "[INFO] Detected Arch Linux. Installing via pacman..."
        sudo pacman -S --noconfirm gnucobol
    else
        echo "[ERROR] Unsupported Linux distribution."
        echo "Please install GnuCOBOL manually using your package manager."
        exit 1
    fi
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if command -v brew &> /dev/null; then
        echo "[INFO] Detected macOS. Installing via Homebrew..."
        brew install gnu-cobol
    else
        echo "[ERROR] Homebrew not found."
        echo "Please install Homebrew first: https://brew.sh"
        echo "Then run: brew install gnu-cobol"
        exit 1
    fi
    
else
    echo "[ERROR] Unsupported operating system: $OSTYPE"
    echo "Please install GnuCOBOL manually."
    exit 1
fi

# Verify installation
if command -v cobc &> /dev/null; then
    echo ""
    echo "[SUCCESS] GnuCOBOL installed successfully!"
    echo "Version: $(cobc --version)"
    echo ""
    echo "You can now run: ./scripts/run_smoke_test.sh"
else
    echo ""
    echo "[ERROR] Installation completed but 'cobc' command not found."
    echo "You may need to restart your terminal or add GnuCOBOL to PATH."
    exit 1
fi
