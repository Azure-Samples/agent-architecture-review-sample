<#
.SYNOPSIS
    Deploy the Architecture Review Agent Web App to Azure App Service (container-based).

.DESCRIPTION
    Creates an Azure Resource Group, Azure Container Registry, App Service Plan,
    and Web App. Builds the Docker image, pushes it to ACR, and configures the
    web app with the required environment variables.

.PARAMETER ResourceGroup
    Name of the Azure resource group (created if it doesn't exist).

.PARAMETER Location
    Azure region (default: eastus2).

.PARAMETER AppName
    Name for the App Service web app. Must be globally unique.

.PARAMETER AcrName
    Name for the Azure Container Registry. Must be globally unique and
    alphanumeric only. Defaults to "${AppName}acr" with hyphens removed.

.PARAMETER SkuPlan
    App Service Plan SKU (default: B1).

.EXAMPLE
    .\deploy\deploy-webapp.ps1 -ResourceGroup arch-review-rg -AppName arch-review-web
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ResourceGroup,

    [Parameter(Mandatory)]
    [string]$AppName,

    [string]$Location = "eastus2",

    [string]$AcrName = ($AppName -replace '[^a-zA-Z0-9]', '') + "acr",

    [string]$SkuPlan = "B1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $ProjectRoot

Write-Host ""
Write-Host "=== Architecture Review Agent — Azure Web App Deployment ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Resource Group : $ResourceGroup"
Write-Host "  App Name       : $AppName"
Write-Host "  ACR Name       : $AcrName"
Write-Host "  Location       : $Location"
Write-Host "  SKU            : $SkuPlan"
Write-Host ""

# ── 1. Verify Azure CLI ─────────────────────────────────────────────────────
Write-Host "[1/8] Checking Azure CLI..." -ForegroundColor Yellow
$azVersion = az version --query '\"azure-cli\"' -o tsv 2>$null
if (-not $azVersion) {
    Write-Host "[ERROR] Azure CLI not found. Install from https://aka.ms/installazurecli" -ForegroundColor Red
    Pop-Location; exit 1
}
Write-Host "  Azure CLI $azVersion" -ForegroundColor Green

# Check login
$account = az account show --query name -o tsv 2>$null
if (-not $account) {
    Write-Host "[..] Not logged in — running az login..." -ForegroundColor Yellow
    az login
}
Write-Host "  Subscription: $(az account show --query name -o tsv)" -ForegroundColor Green

# ── 2. Resource Group ────────────────────────────────────────────────────────
Write-Host "[2/8] Creating resource group '$ResourceGroup'..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output none
Write-Host "  Done." -ForegroundColor Green

# ── 3. Container Registry ───────────────────────────────────────────────────
Write-Host "[3/8] Creating Azure Container Registry '$AcrName'..." -ForegroundColor Yellow
az acr create `
    --resource-group $ResourceGroup `
    --name $AcrName `
    --sku Basic `
    --admin-enabled true `
    --output none
Write-Host "  Done." -ForegroundColor Green

$acrLoginServer = az acr show --name $AcrName --query loginServer -o tsv
Write-Host "  Login server: $acrLoginServer" -ForegroundColor Green

# ── 4. Build & push image ───────────────────────────────────────────────────
Write-Host "[4/8] Building container image via ACR Tasks..." -ForegroundColor Yellow
$imageName = "${acrLoginServer}/arch-review-web:latest"
az acr build `
    --registry $AcrName `
    --image "arch-review-web:latest" `
    --file Dockerfile.web `
    --platform linux/amd64 `
    .
Write-Host "  Image: $imageName" -ForegroundColor Green

# ── 5. App Service Plan ─────────────────────────────────────────────────────
$planName = "${AppName}-plan"
Write-Host "[5/8] Creating App Service Plan '$planName' ($SkuPlan)..." -ForegroundColor Yellow
az appservice plan create `
    --resource-group $ResourceGroup `
    --name $planName `
    --sku $SkuPlan `
    --is-linux `
    --output none
Write-Host "  Done." -ForegroundColor Green

# ── 6. Web App ──────────────────────────────────────────────────────────────
Write-Host "[6/8] Creating Web App '$AppName'..." -ForegroundColor Yellow
az webapp create `
    --resource-group $ResourceGroup `
    --plan $planName `
    --name $AppName `
    --deployment-container-image-name $imageName `
    --output none

# Grant App Service access to ACR
$acrId = az acr show --name $AcrName --query id -o tsv
$principalId = az webapp identity assign `
    --resource-group $ResourceGroup `
    --name $AppName `
    --query principalId -o tsv

az role assignment create `
    --assignee $principalId `
    --role AcrPull `
    --scope $acrId `
    --output none

# Configure ACR auth via managed identity
az webapp config set `
    --resource-group $ResourceGroup `
    --name $AppName `
    --generic-configurations '{\"acrUseManagedIdentityCreds\": true}' `
    --output none

Write-Host "  Done." -ForegroundColor Green

# ── 7. Configure app settings ───────────────────────────────────────────────
Write-Host "[7/8] Configuring app settings..." -ForegroundColor Yellow

# Read from .env if it exists
$envFile = Join-Path $ProjectRoot ".env"
$settings = @("WEBSITES_PORT=8000")

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            # Strip surrounding quotes from values
            if ($line -match '^([^=]+)=(.*)$') {
                $key = $Matches[1].Trim()
                $val = $Matches[2].Trim().Trim('"').Trim("'")
                $settings += "${key}=${val}"
            }
        }
    }
    Write-Host "  Loaded settings from .env" -ForegroundColor Green
} else {
    Write-Host "  [WARN] No .env file found. Set app settings manually." -ForegroundColor Yellow
    $settings += "MODEL_DEPLOYMENT_NAME=gpt-4.1"
}

az webapp config appsettings set `
    --resource-group $ResourceGroup `
    --name $AppName `
    --settings @settings `
    --output none

Write-Host "  Done." -ForegroundColor Green

# ── 8. Restart & show URL ───────────────────────────────────────────────────
Write-Host "[8/8] Restarting web app..." -ForegroundColor Yellow
az webapp restart --resource-group $ResourceGroup --name $AppName --output none

$url = "https://${AppName}.azurewebsites.net"
Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Web App URL  : $url" -ForegroundColor Green
Write-Host "  Health Check : $url/api/health" -ForegroundColor Green
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host ""
Write-Host "To view logs:" -ForegroundColor White
Write-Host "  az webapp log tail --resource-group $ResourceGroup --name $AppName" -ForegroundColor White
Write-Host ""
Write-Host "To update after code changes:" -ForegroundColor White
Write-Host "  az acr build --registry $AcrName --image arch-review-web:latest --file Dockerfile.web ." -ForegroundColor White
Write-Host "  az webapp restart --resource-group $ResourceGroup --name $AppName" -ForegroundColor White
Write-Host ""

Pop-Location
