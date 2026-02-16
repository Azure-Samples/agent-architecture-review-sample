<#
.SYNOPSIS
    Deploy the Architecture Review Agent as a Hosted Agent on Microsoft Foundry.

.DESCRIPTION
    Provisions the required Azure resources (AI Services account, Microsoft Foundry
    project, model deployment), deploys the hosted agent container via
    Azure Developer CLI (azd), and configures RBAC for the managed identity.

.PARAMETER ResourceGroup
    Name of the Azure resource group.

.PARAMETER ProjectName
    Name for the Microsoft Foundry project. Defaults to "arch-review".

.PARAMETER Location
    Azure region (default: eastus2).

.PARAMETER ModelName
    Model to deploy (default: gpt-4.1).

.EXAMPLE
    .\scripts\windows\deploy.ps1 -target agent -ResourceGroup arch-review-rg -ProjectName arch-review
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ResourceGroup,

    [string]$ProjectName = "arch-review",

    [string]$Location = "eastus2",

    [string]$ModelName = "gpt-4.1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Get script directory, then go up 2 levels: scripts/windows -> scripts -> project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
Push-Location $ProjectRoot

Write-Host ""
Write-Host "=== Architecture Review Agent — Hosted Agent Deployment ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Resource Group : $ResourceGroup"
Write-Host "  Project Name   : $ProjectName"
Write-Host "  Location       : $Location"
Write-Host "  Model          : $ModelName"
Write-Host ""

# ── 1. Verify prerequisites ─────────────────────────────────────────────────
Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Yellow

# Azure CLI
$azVersion = az version --query '\"azure-cli\"' -o tsv 2>$null
if (-not $azVersion) {
    Write-Host "[ERROR] Azure CLI not found. Install: winget install Microsoft.AzureCLI" -ForegroundColor Red
    Pop-Location; exit 1
}
Write-Host "  Azure CLI $azVersion" -ForegroundColor Green

# Azure Developer CLI
$azdVersion = azd version 2>$null
if (-not $azdVersion) {
    Write-Host "[ERROR] Azure Developer CLI (azd) not found. Install: winget install Microsoft.Azd" -ForegroundColor Red
    Pop-Location; exit 1
}
Write-Host "  azd $azdVersion" -ForegroundColor Green

# Login
$account = az account show --query name -o tsv 2>$null
if (-not $account) {
    Write-Host "[..] Running az login..." -ForegroundColor Yellow
    az login
}
Write-Host "  Subscription: $(az account show --query name -o tsv)" -ForegroundColor Green

# azd auth
try {
    azd auth login --check-status 2>$null | Out-Null
} catch {
    Write-Host "[..] Running azd auth login..." -ForegroundColor Yellow
    azd auth login
}
Write-Host "  azd authenticated." -ForegroundColor Green

# ── 2. Resource Group ────────────────────────────────────────────────────────
Write-Host "[2/6] Creating resource group '$ResourceGroup'..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output none
Write-Host "  Done." -ForegroundColor Green

# ── 3. Provision AI Services + Project ───────────────────────────────────────
Write-Host "[3/6] Provisioning Azure AI Services..." -ForegroundColor Yellow

$aiAccountName = "${ProjectName}-ai"

# Create Azure AI Services (multi-service) account
$existingAccount = az cognitiveservices account list `
    --resource-group $ResourceGroup `
    --query "[?name=='$aiAccountName'].name" -o tsv 2>$null

if (-not $existingAccount) {
    az cognitiveservices account create `
        --name $aiAccountName `
        --resource-group $ResourceGroup `
        --kind AIServices `
        --sku S0 `
        --location $Location `
        --output none
    Write-Host "  Created AI Services account: $aiAccountName" -ForegroundColor Green
} else {
    Write-Host "  AI Services account '$aiAccountName' already exists." -ForegroundColor Green
}

# Get the endpoint
$aiEndpoint = az cognitiveservices account show `
    --name $aiAccountName `
    --resource-group $ResourceGroup `
    --query properties.endpoint -o tsv

Write-Host "  Endpoint: $aiEndpoint" -ForegroundColor Green

# ── 4. Deploy model ─────────────────────────────────────────────────────────
Write-Host "[4/6] Deploying model '$ModelName'..." -ForegroundColor Yellow

$existingDeployment = az cognitiveservices account deployment list `
    --name $aiAccountName `
    --resource-group $ResourceGroup `
    --query "[?name=='$ModelName'].name" -o tsv 2>$null

if (-not $existingDeployment) {
    az cognitiveservices account deployment create `
        --name $aiAccountName `
        --resource-group $ResourceGroup `
        --deployment-name $ModelName `
        --model-name $ModelName `
        --model-version "2024-08-06" `
        --model-format OpenAI `
        --sku-capacity 30 `
        --sku-name Standard `
        --output none
    Write-Host "  Deployed model: $ModelName" -ForegroundColor Green
} else {
    Write-Host "  Model deployment '$ModelName' already exists." -ForegroundColor Green
}

# ── 5. Deploy hosted agent via azd ──────────────────────────────────────────
Write-Host "[5/6] Deploying hosted agent with azd..." -ForegroundColor Yellow

# Set environment variables for azd
$env:AZURE_AI_PROJECT_ENDPOINT = $aiEndpoint
$env:MODEL_DEPLOYMENT_NAME = $ModelName

azd ai agent deploy
Write-Host "  Agent deployed." -ForegroundColor Green

# ── 6. Configure RBAC ───────────────────────────────────────────────────────
Write-Host "[6/6] Configuring RBAC..." -ForegroundColor Yellow

$scope = az cognitiveservices account show `
    --name $aiAccountName `
    --resource-group $ResourceGroup `
    --query id -o tsv

Write-Host ""
Write-Host "  The hosted agent uses a system-assigned managed identity." -ForegroundColor White
Write-Host "  After deployment, assign the 'Azure AI User' role:" -ForegroundColor White
Write-Host ""
Write-Host "    az role assignment create ``" -ForegroundColor White
Write-Host "      --assignee <MANAGED_IDENTITY_PRINCIPAL_ID> ``" -ForegroundColor White
Write-Host "      --role 'Azure AI User' ``" -ForegroundColor White
Write-Host "      --scope $scope" -ForegroundColor White
Write-Host ""
Write-Host "  Find the Principal ID in Microsoft Foundry portal → Hosted Agents → Architecture Review Agent → Details." -ForegroundColor Yellow

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Hosted Agent Deployment Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  AI Endpoint  : $aiEndpoint" -ForegroundColor Green
Write-Host "  Model        : $ModelName" -ForegroundColor Green
Write-Host ""
Write-Host "Test with:" -ForegroundColor White
Write-Host '  $token = az account get-access-token --resource "https://cognitiveservices.azure.com" --query accessToken -o tsv' -ForegroundColor White
Write-Host "  Invoke-RestMethod -Uri `"$($aiEndpoint)openai/responses?api-version=2025-05-15-preview`" ``" -ForegroundColor White
Write-Host '    -Method POST -Headers @{ Authorization = "Bearer $token" } `' -ForegroundColor White
Write-Host '    -ContentType "application/json" `' -ForegroundColor White
Write-Host '    -Body ''{"input":{"messages":[{"role":"user","content":"Review: LB -> API -> DB"}]}}''' -ForegroundColor White
Write-Host ""
Write-Host "For the full RBAC and testing guide, see deployment.md" -ForegroundColor White
Write-Host ""

Pop-Location
