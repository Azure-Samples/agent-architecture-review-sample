#!/usr/bin/env bash
# Architecture Review Agent — Unified Deploy Script
#
# Routes to either deploy-agent.sh or deploy-webapp.sh based on --target parameter.
#
# Usage:
#   bash scripts/linux-mac/deploy.sh --target agent [other args]
#   bash scripts/linux-mac/deploy.sh --target webapp --resource-group <rg> --app-name <name> [other args]
#
# Default: agent

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
TARGET="agent"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Parse target argument ────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        *)
            # Pass remaining args to the target script
            break
            ;;
    esac
done

# ── Validate target ──────────────────────────────────────────────────────────
case "$TARGET" in
    agent)
        echo "🚀 Deploying hosted agent..."
        exec bash "$SCRIPT_DIR/deploy-agent.sh" "$@"
        ;;
    webapp)
        echo "🚀 Deploying web app..."
        exec bash "$SCRIPT_DIR/deploy-webapp.sh" "$@"
        ;;
    *)
        echo "❌ Unknown target: $TARGET"
        echo "Usage: bash deploy.sh --target {agent|webapp} [other args]"
        exit 1
        ;;
esac
