#!/usr/bin/env bash
# Architecture Review Agent — Start both FastAPI backend and React frontend for local development.
# Runs the FastAPI backend on port 8000 and the Vite React dev server on port 5173.
# The Vite dev server proxies /api requests to the backend.
#
# Usage:
#   chmod +x scripts/linux-mac/dev.sh
#   bash scripts/linux-mac/dev.sh

set -euo pipefail

# Go up 2 levels: scripts/linux-mac -> scripts -> project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "=== Architecture Review Agent Dev Server ==="
echo ""

# ── 1. Check prerequisites ──────────────────────────────────────────────────
if [ ! -f ".venv/bin/activate" ]; then
    echo "[ERROR] .venv not found. Run bash scripts/linux-mac/setup.sh first."
    exit 1
fi

FRONTEND_DIR="$SCRIPT_DIR/frontend"
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "[..] Installing frontend dependencies..."
    (cd "$FRONTEND_DIR" && npm install)
fi

# ── 2. Activate Python venv ─────────────────────────────────────────────────
echo "[..] Activating Python virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

# ── 3. Start FastAPI backend (background) ───────────────────────────────────
echo "[..] Starting FastAPI backend on http://localhost:8000 ..."
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# ── 4. Trap to clean up background process ──────────────────────────────────
cleanup() {
    echo ""
    echo "[..] Shutting down backend (PID $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    echo "[OK] All servers stopped."
}
trap cleanup EXIT INT TERM

# ── 5. Start Vite frontend (foreground) ─────────────────────────────────────
echo "[..] Starting React dev server on http://localhost:5173 ..."
echo ""
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000/api/health"
echo "  Press Ctrl+C to stop both servers."
echo ""

cd "$FRONTEND_DIR"
npx vite --host
