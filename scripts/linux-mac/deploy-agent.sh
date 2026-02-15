#!/usr/bin/env bash
# Architecture Review Agent — Deploy Hosted Agent to Azure AI Foundry.
#
# Provisions Azure AI Services, deploys a model, and deploys the hosted
# agent container via Azure Developer CLI (azd).
#
# Usage:
#   chmod +x scripts/linux-mac/deploy.sh
#   bash scripts/linux-mac/deploy.sh --target agent \
#       --resource-group arch-review-rg \
#       --project-name arch-review \
#       --location eastus2

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
RESOURCE_GROUP=""
PROJECT_NAME="arch-review"
LOCATION="eastus2"
MODEL_NAME="gpt-4.1"

# ── Parse arguments ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --resource-group|-g) RESOURCE_GROUP="$2"; shift 2 ;;
        --project-name|-p)   PROJECT_NAME="$2";   shift 2 ;;
        --location|-l)       LOCATION="$2";       shift 2 ;;
        --model-name|-m)     MODEL_NAME="$2";      shift 2 ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --resource-group <rg> [--project-name <name>] [--location <region>] [--model <model>]"
            exit 1 ;;
    esac
done

if [[ -z "$RESOURCE_GROUP" ]]; then
    echo "Error: --resource-group is required."
    exit 1
fi

AI_ACCOUNT_NAME="${PROJECT_NAME}-ai"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo "=== Architecture Review Agent — Hosted Agent Deployment ==="
echo ""
echo "  Resource Group : $RESOURCE_GROUP"
echo "  Project Name   : $PROJECT_NAME"
echo "  Location       : $LOCATION"
echo "  Model          : $MODEL_NAME"
echo ""

# ── 1. Verify prerequisites ─────────────────────────────────────────────────
echo "[1/6] Checking prerequisites..."

if ! command -v az &>/dev/null; then
    echo "[ERROR] Azure CLI not found. Install: https://aka.ms/installazurecli"
    exit 1
fi
echo "  Azure CLI $(az version --query '"azure-cli"' -o tsv)"

# Azure Developer CLI (optional for hosted agent deployment)
AZD_AVAILABLE=false
if ! command -v azd &>/dev/null; then
    echo "  [WARNING] Azure Developer CLI (azd) not found."
    echo "  Hosted agent deployment will be skipped. Install: curl -fsSL https://aka.ms/install-azd.sh | bash"
else
    echo "  azd $(azd version)"
    AZD_AVAILABLE=true
    
    azd auth login --check-status &>/dev/null || azd auth login
    echo "  azd authenticated."
fi

if ! az account show &>/dev/null; then
    echo "[..] Running az login..."
    az login
fi
echo "  Subscription: $(az account show --query name -o tsv)"

# ── 2. Resource Group ────────────────────────────────────────────────────────
echo "[2/6] Creating resource group '$RESOURCE_GROUP'..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
echo "  Done."

# ── 3. Provision AI Services ────────────────────────────────────────────────
echo "[3/6] Provisioning Azure AI Services..."

EXISTING=$(az cognitiveservices account list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?name=='$AI_ACCOUNT_NAME'].name" -o tsv 2>/dev/null || true)

if [[ -z "$EXISTING" ]]; then
    az cognitiveservices account create \
        --name "$AI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --kind AIServices \
        --sku S0 \
        --location "$LOCATION" \
        --output none
    echo "  Created AI Services account: $AI_ACCOUNT_NAME"
else
    echo "  AI Services account '$AI_ACCOUNT_NAME' already exists."
fi

AI_ENDPOINT=$(az cognitiveservices account show \
    --name "$AI_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.endpoint -o tsv)

echo "  Endpoint: $AI_ENDPOINT"

# ── 4. Deploy model ─────────────────────────────────────────────────────────
echo "[4/6] Deploying model '$MODEL_NAME'..."

EXISTING_DEPLOY=$(az cognitiveservices account deployment list \
    --name "$AI_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?name=='$MODEL_NAME'].name" -o tsv 2>/dev/null || true)

if [[ -z "$EXISTING_DEPLOY" ]]; then
    if ! az cognitiveservices account deployment create \
        --name "$AI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --deployment-name "$MODEL_NAME" \
        --model-name "$MODEL_NAME" \
        --model-version "2025-04-14" \
        --model-format OpenAI \
        --sku-capacity 30 \
        --sku-name Standard \
        --output none 2>&1; then
        echo "  [ERROR] Failed to deploy model. The model may not be supported in this region."
        echo "  Try a different model (e.g., gpt-4, gpt-35-turbo) or region."
        exit 1
    fi
    echo "  Deployed model: $MODEL_NAME"
else
    echo "  Model deployment '$MODEL_NAME' already exists."
fi

# ── 5. Deploy hosted agent ──────────────────────────────────────────────────
echo "[5/6] Deploying hosted agent with azd..."

if [ "$AZD_AVAILABLE" = false ]; then
    echo "  [SKIPPED] azd not available."
    echo "  Azure resources are provisioned. Deploy agent manually via Azure AI Foundry portal."
else
    # Initialize azd environment if not already done
    if [ ! -d ".azure" ]; then
        echo "  [..] Initializing azd environment..."
        azd init --subscription "$(az account show --query id -o tsv)" \
            --location "$LOCATION" \
            --environment "${PROJECT_NAME}-env" &>/dev/null
    fi
    
    # Initialize agent with agent.yaml
    if [ -f "agent.yaml" ]; then
        echo "  [..] Initializing azd AI agent configuration..."
        
        export AZURE_AI_PROJECT_ENDPOINT="$AI_ENDPOINT"
        export MODEL_DEPLOYMENT_NAME="$MODEL_NAME"
        export AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
        export AZURE_RESOURCE_GROUP="$RESOURCE_GROUP"
        
        if azd ai agent init -m agent.yaml 2>&1; then
            echo "  [..] Deploying agent..."
            if azd deploy 2>&1; then
                echo "  Agent deployed successfully."
            else
                echo "  [ERROR] Failed to deploy hosted agent."
                echo "  Azure resources are provisioned. Deploy agent manually via Azure AI Foundry portal."
            fi
        else
            echo "  [ERROR] Failed to initialize azd agent configuration."
            echo "  Deploy agent manually via Azure AI Foundry portal."
        fi
    else
        echo "  [SKIPPED] agent.yaml not found in current directory."
        echo "  Deploy agent manually via Azure AI Foundry portal or place agent.yaml in project root."
    fi
fi

# ── 6. RBAC guidance ────────────────────────────────────────────────────────
SCOPE=$(az cognitiveservices account show \
    --name "$AI_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query id -o tsv)

echo "[6/6] RBAC configuration..."
echo ""
echo "  The hosted agent uses a system-assigned managed identity."
echo "  After deployment, assign the 'Azure AI User' role:"
echo ""
echo "    az role assignment create \\"
echo "      --assignee <MANAGED_IDENTITY_PRINCIPAL_ID> \\"
echo "      --role 'Azure AI User' \\"
echo "      --scope $SCOPE"
echo ""
echo "  Find the Principal ID in Azure AI Foundry portal → Hosted Agents → Architecture Review Agent → Details."

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "=== Hosted Agent Deployment Complete ==="
echo ""
echo "  AI Endpoint  : $AI_ENDPOINT"
echo "  Model        : $MODEL_NAME"
echo ""
echo "Test with:"
echo "  TOKEN=\$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)"
echo "  curl -X POST '${AI_ENDPOINT}openai/responses?api-version=2025-05-15-preview' \\"
echo "    -H \"Authorization: Bearer \$TOKEN\" \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"input\":{\"messages\":[{\"role\":\"user\",\"content\":\"Review: LB -> API -> DB\"}]}}'"
echo ""
echo "For the full RBAC and testing guide, see deployment.md"
echo ""
