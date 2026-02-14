<#
.SYNOPSIS
    Tear down all Architecture Review Agent Azure resources.

.DESCRIPTION
    Deletes the entire resource group, removing all resources created by
    the deployment scripts (App Service, ACR, AI Services, etc.).

.PARAMETER ResourceGroup
    Name of the Azure resource group to delete.

.PARAMETER Force
    Skip confirmation prompt.

.EXAMPLE
    .\scripts\windows\teardown.ps1 -ResourceGroup arch-review-rg
    .\scripts\windows\teardown.ps1 -ResourceGroup arch-review-rg -Force
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ResourceGroup,

    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Architecture Review Agent — Teardown ===" -ForegroundColor Red
Write-Host ""

# List what will be deleted
Write-Host "Resources in '$ResourceGroup':" -ForegroundColor Yellow
az resource list --resource-group $ResourceGroup --query "[].{Name:name, Type:type}" -o table

if (-not $Force) {
    Write-Host ""
    $confirm = Read-Host "Delete resource group '$ResourceGroup' and ALL its resources? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Aborted." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host ""
Write-Host "Deleting resource group '$ResourceGroup'..." -ForegroundColor Yellow
az group delete --name $ResourceGroup --yes --no-wait
Write-Host ""
Write-Host "[OK] Resource group deletion initiated (runs in background)." -ForegroundColor Green
Write-Host "     Monitor: az group show --name $ResourceGroup --query properties.provisioningState -o tsv" -ForegroundColor White
Write-Host ""
