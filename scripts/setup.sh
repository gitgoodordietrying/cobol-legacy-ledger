#!/bin/bash
#================================================================*
# setup.sh — Initialize Python environment and dependencies
# Usage: ./scripts/setup.sh
#================================================================*

set -e

echo "Setting up Python environment..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found"
    exit 1
fi

python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "  Python $python_version"

# Create venv if it doesn't exist
if [ ! -d "python/venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv python/venv
fi

# Activate venv
source python/venv/bin/activate

# Install dependencies
echo "  Installing dependencies..."
pip install --quiet -r python/requirements.txt

echo ""
echo "✓ Python environment ready!"
echo ""
echo "To activate: source python/venv/bin/activate"
echo "To run CLI: python -m python.cli --help"
