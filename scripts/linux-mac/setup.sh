#!/usr/bin/env bash
# Architecture Review Agent — One-click setup script for Linux / macOS.
# Creates a .venv virtual environment, installs dependencies,
# and copies .env.template to .env if it doesn't exist.
#
# Usage:
#   chmod +x scripts/linux-mac/setup.sh
#   bash scripts/linux-mac/setup.sh

set -euo pipefail

# Go up 2 levels: scripts/linux-mac -> scripts -> project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "=== Architecture Review Agent Setup ==="
echo ""

# ── 1. Check Python ──────────────────────────────────────────────────────────
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1)
        major=$("$candidate" -c "import sys; print(sys.version_info.major)")
        minor=$("$candidate" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$candidate"
            echo "[OK] Found $ver"
            break
        else
            echo "[WARN] $ver found but Python 3.11+ is required."
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python 3.11+ is required but was not found on PATH."
    echo "        Install from https://www.python.org/downloads/"
    exit 1
fi

# ── 2. Check Azure Developer CLI (azd) ──────────────────────────────────────
echo ""
if ! command -v azd &>/dev/null; then
    echo "[WARN] Azure Developer CLI (azd) not found."
    echo "[..] Attempting to install azd..."
    
    # Install azd
    if curl -fsSL https://aka.ms/install-azd.sh | bash; then
        # Source profile to get azd in PATH
        if [ -f "$HOME/.bashrc" ]; then
            # shellcheck disable=SC1091
            source "$HOME/.bashrc" 2>/dev/null || true
        fi
        if [ -f "$HOME/.zshrc" ]; then
            # shellcheck disable=SC1091
            source "$HOME/.zshrc" 2>/dev/null || true
        fi
        
        if command -v azd &>/dev/null; then
            echo "[OK] Azure Developer CLI installed successfully: $(azd version)"
        else
            echo "[WARN] azd installed but not in PATH. Restart terminal or run: source ~/.bashrc"
        fi
    else
        echo "[WARN] Failed to install azd. Install manually: curl -fsSL https://aka.ms/install-azd.sh | bash"
    fi
else
    echo "[OK] Found $(azd version)"
    
    # Check if azd supports AI agent commands
    if azd ai --help 2>&1 | grep -q "agent"; then
        echo "[OK] azd AI agent support detected."
    else
        echo "[WARN] azd AI agent commands not available. Update azd to the latest version."
    fi
fi

# ── 3. Create .venv ──────────────────────────────────────────────────────────
if [ -d ".venv" ]; then
    echo "[OK] Virtual environment already exists at .venv/"
else
    echo "[..] Creating virtual environment (.venv)..."
    "$PYTHON" -m venv .venv
    echo "[OK] Created .venv/"
fi

# ── 4. Activate & install dependencies ────────────────────────────────────────
echo "[..] Activating virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[..] Upgrading pip..."
python -m pip install --upgrade pip --quiet

echo "[..] Installing dependencies from requirements.txt..."
python -m pip install -r requirements.txt

echo "[OK] Dependencies installed."

# ── 5. Copy .env.template → .env (if needed) ─────────────────────────────────
if [ ! -f ".env" ]; then
    if [ -f ".env.template" ]; then
        cp .env.template .env
        echo "[OK] Created .env from .env.template — edit it with your settings."
    else
        echo "[WARN] No .env.template found. Create a .env file manually."
    fi
else
    echo "[OK] .env already exists."
fi

# ── 6. Create output directory ─────────────────────────────────────────────────────────────
if [ ! -d "output" ]; then
    mkdir -p output
    echo "[OK] Created output/ directory"
else
    echo "[OK] output/ directory already exists."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Setup Complete ==="
echo ""
echo "To activate the environment in future sessions:"
echo "  source .venv/bin/activate"
echo ""
echo "Quick start (CLI):"
echo "  python run_local.py examples/ecommerce.yaml"
echo ""
echo "Quick start (Web UI):"
echo "  bash scripts/linux-mac/dev.sh"
echo ""
