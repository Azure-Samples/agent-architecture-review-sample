<#
.SYNOPSIS
    Deploy Architecture Review Agent to Azure (unified deploy script).

.DESCRIPTION
    Routes to either deploy-agent.ps1 or deploy-webapp.ps1 based on -target parameter.
    Default deployment target is "agent" (Hosted Agent).

.PARAMETER target
    Deployment target: 'agent' (default) or 'webapp'.

.PARAMETER ResourceGroup
    Name of the Azure resource group (passed to target script).

.PARAMETER ProjectName
    Name for the AI Foundry project (passed to target script).

.PARAMETER Location
    Azure region (passed to target script).

.PARAMETER ModelName
    Model to deploy (passed to target script).

.EXAMPLE
    # Deploy Hosted Agent (default)
    .\scripts\windows\deploy.ps1 -ResourceGroup arch-review-rg

    # Deploy Hosted Agent (explicit)
    .\scripts\windows\deploy.ps1 -target agent -ResourceGroup arch-review-rg

    # Deploy Web App
    .\scripts\windows\deploy.ps1 -target webapp -ResourceGroup arch-review-rg
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("agent", "webapp")]
    [string]$target = "agent",

    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup,

    [Parameter(Mandatory=$false)]
    [string]$ProjectName = "arch-review",

    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus2",

    [Parameter(Mandatory=$false)]
    [string]$ModelName = "gpt-4.1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Prepare arguments for target script
$args = @()
if ($ResourceGroup) { $args += @("-ResourceGroup", $ResourceGroup) }
$args += @("-ProjectName", $ProjectName)
$args += @("-Location", $Location)
$args += @("-ModelName", $ModelName)

# Route to appropriate script
Write-Host ""
if ($target -eq "agent") {
    Write-Host "🚀 Deploying Hosted Agent..." -ForegroundColor Cyan
    & "$scriptDir/deploy-agent.ps1" @args
} else {
    Write-Host "🚀 Deploying Web App..." -ForegroundColor Cyan
    & "$scriptDir/deploy-webapp.ps1" @args
}
