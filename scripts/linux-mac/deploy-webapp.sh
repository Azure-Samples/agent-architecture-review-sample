#!/usr/bin/env bash
# Architecture Review Agent — Deploy Web App to Azure App Service (container-based).
#
# Creates an Azure Resource Group, Container Registry, App Service Plan,
# and Web App. Builds the Docker image via ACR Tasks, pushes it, and
# configures the web app with environment variables from .env.
#
# Usage:
#   chmod +x scripts/linux-mac/deploy.sh
#   bash scripts/linux-mac/deploy.sh --target webapp \
#       --resource-group arch-review-rg \
#       --app-name arch-review-web \
#       --location eastus2

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
RESOURCE_GROUP=""
APP_NAME=""
LOCATION="eastus2"
ACR_NAME=""
SKU="B1"

# ── Parse arguments ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --resource-group|-g) RESOURCE_GROUP="$2"; shift 2 ;;
        --app-name|-n)       APP_NAME="$2";       shift 2 ;;
        --location|-l)       LOCATION="$2";       shift 2 ;;
        --acr-name)          ACR_NAME="$2";       shift 2 ;;
        --sku)               SKU="$2";            shift 2 ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --resource-group <rg> --app-name <name> [--location <region>] [--acr-name <acr>] [--sku <sku>]"
            exit 1 ;;
    esac
done

if [[ -z "$RESOURCE_GROUP" || -z "$APP_NAME" ]]; then
    echo "Error: --resource-group and --app-name are required."
    echo "Usage: $0 --resource-group <rg> --app-name <name>"
    exit 1
fi

[[ -z "$ACR_NAME" ]] && ACR_NAME="$(echo "${APP_NAME}" | tr -d '-')acr"
PLAN_NAME="${APP_NAME}-plan"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo "=== Architecture Review Agent — Azure Web App Deployment ==="
echo ""
echo "  Resource Group : $RESOURCE_GROUP"
echo "  App Name       : $APP_NAME"
echo "  ACR Name       : $ACR_NAME"
echo "  Location       : $LOCATION"
echo "  SKU            : $SKU"
echo ""

# ── 1. Verify Azure CLI ─────────────────────────────────────────────────────
echo "[1/8] Checking Azure CLI..."
if ! command -v az &>/dev/null; then
    echo "[ERROR] Azure CLI not found. Install from https://aka.ms/installazurecli"
    exit 1
fi
echo "  Azure CLI $(az version --query '\"azure-cli\"' -o tsv)"

if ! az account show &>/dev/null; then
    echo "[..] Not logged in — running az login..."
    az login
fi
echo "  Subscription: $(az account show --query name -o tsv)"

# ── 2. Resource Group ────────────────────────────────────────────────────────
echo "[2/8] Creating resource group '$RESOURCE_GROUP'..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
echo "  Done."

# ── 3. Container Registry ───────────────────────────────────────────────────
echo "[3/8] Creating Azure Container Registry '$ACR_NAME'..."
az acr create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --sku Basic \
    --admin-enabled true \
    --output none

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
echo "  Login server: $ACR_LOGIN_SERVER"

# ── 4. Build & push image ───────────────────────────────────────────────────
echo "[4/8] Building container image via ACR Tasks..."
IMAGE_NAME="${ACR_LOGIN_SERVER}/arch-review-web:latest"

az acr build \
    --registry "$ACR_NAME" \
    --image "arch-review-web:latest" \
    --file Dockerfile.web \
    --platform linux/amd64 \
    .

echo "  Image: $IMAGE_NAME"

# ── 5. App Service Plan ─────────────────────────────────────────────────────
echo "[5/8] Creating App Service Plan '$PLAN_NAME' ($SKU)..."
az appservice plan create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$PLAN_NAME" \
    --sku "$SKU" \
    --is-linux \
    --output none
echo "  Done."

# ── 6. Web App ──────────────────────────────────────────────────────────────
echo "[6/8] Creating Web App '$APP_NAME'..."
az webapp create \
    --resource-group "$RESOURCE_GROUP" \
    --plan "$PLAN_NAME" \
    --name "$APP_NAME" \
    --deployment-container-image-name "$IMAGE_NAME" \
    --output none

# Grant App Service access to ACR via managed identity
ACR_ID=$(az acr show --name "$ACR_NAME" --query id -o tsv)
PRINCIPAL_ID=$(az webapp identity assign \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query principalId -o tsv)

az role assignment create \
    --assignee "$PRINCIPAL_ID" \
    --role AcrPull \
    --scope "$ACR_ID" \
    --output none

az webapp config set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --generic-configurations '{"acrUseManagedIdentityCreds": true}' \
    --output none

echo "  Done."

# ── 7. Configure app settings ───────────────────────────────────────────────
echo "[7/8] Configuring app settings..."

SETTINGS=("WEBSITES_PORT=8000")

ENV_FILE="${PROJECT_ROOT}/.env"
if [[ -f "$ENV_FILE" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="$(echo "$line" | xargs)"     # trim whitespace
        [[ -z "$line" || "$line" == \#* ]] && continue
        key="${line%%=*}"
        val="${line#*=}"
        val="$(echo "$val" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
        SETTINGS+=("${key}=${val}")
    done < "$ENV_FILE"
    echo "  Loaded settings from .env"
else
    echo "  [WARN] No .env file found. Set app settings manually."
    SETTINGS+=("MODEL_DEPLOYMENT_NAME=gpt-4.1")
fi

az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --settings "${SETTINGS[@]}" \
    --output none

echo "  Done."

# ── 8. Restart & show URL ───────────────────────────────────────────────────
echo "[8/8] Restarting web app..."
az webapp restart --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --output none

URL="https://${APP_NAME}.azurewebsites.net"
echo ""
echo "=== Deployment Complete ==="
echo ""
echo "  Web App URL  : $URL"
echo "  Health Check : $URL/api/health"
echo "  Resource Group: $RESOURCE_GROUP"
echo ""
echo "To view logs:"
echo "  az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
echo ""
echo "To update after code changes:"
echo "  az acr build --registry $ACR_NAME --image arch-review-web:latest --file Dockerfile.web ."
echo "  az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME"
echo ""
