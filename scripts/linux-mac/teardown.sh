#!/usr/bin/env bash
# Architecture Review Agent — Tear down all Azure resources.
#
# Deletes the entire resource group, removing all resources created by
# the deployment scripts.
#
# Usage:
#   bash scripts/linux-mac/teardown.sh --resource-group arch-review-rg
#   bash scripts/linux-mac/teardown.sh --resource-group arch-review-rg --force

set -euo pipefail

RESOURCE_GROUP=""
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --resource-group|-g) RESOURCE_GROUP="$2"; shift 2 ;;
        --force|-f)          FORCE=true;          shift ;;
        *)
            echo "Usage: $0 --resource-group <rg> [--force]"
            exit 1 ;;
    esac
done

if [[ -z "$RESOURCE_GROUP" ]]; then
    echo "Error: --resource-group is required."
    exit 1
fi

echo ""
echo "=== Architecture Review Agent — Teardown ==="
echo ""

echo "Resources in '$RESOURCE_GROUP':"
az resource list --resource-group "$RESOURCE_GROUP" \
    --query "[].{Name:name, Type:type}" -o table

if [[ "$FORCE" != true ]]; then
    echo ""
    read -rp "Delete resource group '$RESOURCE_GROUP' and ALL its resources? (yes/no): " CONFIRM
    if [[ "$CONFIRM" != "yes" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo ""
echo "Deleting resource group '$RESOURCE_GROUP'..."
az group delete --name "$RESOURCE_GROUP" --yes --no-wait
echo ""
echo "[OK] Resource group deletion initiated (runs in background)."
echo "     Monitor: az group show --name $RESOURCE_GROUP --query properties.provisioningState -o tsv"
echo ""
