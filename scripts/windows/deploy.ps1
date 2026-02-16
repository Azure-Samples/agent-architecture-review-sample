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
    Name for the Microsoft Foundry project (used for agent deployments).

.PARAMETER AppName
    Name for the App Service web app (used for webapp deployments).

.PARAMETER Location
    Azure region (passed to target script).

.PARAMETER ModelName
    Model to deploy (used for agent deployments).

.EXAMPLE
    # Deploy Hosted Agent (default)
    .\scripts\windows\deploy.ps1 -ResourceGroup arch-review-rg

    # Deploy Hosted Agent (explicit)
    .\scripts\windows\deploy.ps1 -target agent -ResourceGroup arch-review-rg

    # Deploy Web App
    .\scripts\windows\deploy.ps1 -target webapp -ResourceGroup arch-review-rg -AppName arch-review-web
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("agent", "webapp")]
    [string]$target = "agent",

    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory=$false)]
    [string]$ProjectName = "arch-review",

    [Parameter(Mandatory=$false)]
    [string]$AppName,

    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus2",

    [Parameter(Mandatory=$false)]
    [string]$ModelName = "gpt-4.1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Route to appropriate script
Write-Host ""
if ($target -eq "agent") {
    # Prepare arguments for Hosted Agent deployment
    $agentArgs = @()
    if ($ResourceGroup) { $agentArgs += @("-ResourceGroup", $ResourceGroup) }
    $agentArgs += @("-ProjectName", $ProjectName)
    $agentArgs += @("-Location", $Location)
    $agentArgs += @("-ModelName", $ModelName)

    Write-Host "🚀 Deploying Hosted Agent..." -ForegroundColor Cyan
    & "$scriptDir/deploy-agent.ps1" @agentArgs
} else {
    # Prepare arguments for Web App deployment
    $webappArgs = @()
    if ($ResourceGroup) { $webappArgs += @("-ResourceGroup", $ResourceGroup) }
    
    # Use AppName if provided, otherwise fall back to ProjectName for backward compatibility
    $webAppName = if ($AppName) { $AppName } else { $ProjectName }
    $webappArgs += @("-AppName", $webAppName)
    $webappArgs += @("-Location", $Location)

    Write-Host "🚀 Deploying Web App..." -ForegroundColor Cyan
    & "$scriptDir/deploy-webapp.ps1" @webappArgs
}
