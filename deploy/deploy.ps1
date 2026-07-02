# Deploy to server from PowerShell:
#   1. cp .env.example .env  (fill in secrets)
#   2. .\deploy\deploy.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Error "Create .env from .env.example first"
}

$Server = "root@178.17.52.193"
$Remote = "/opt/pass24-telegram-bot"

Write-Host "==> mkdir on server"
ssh -o StrictHostKeyChecking=accept-new $Server "mkdir -p $Remote"

Write-Host "==> upload files"
scp -r pass24_api_client bot requirements.txt deploy README.md docs .env.example .gitattributes "${Server}:${Remote}/"

Write-Host "==> upload .env"
scp $envFile "${Server}:${Remote}/.env"

Write-Host "==> run install.sh on server"
ssh $Server "sed -i 's/\r$//' $Remote/deploy/install.sh && bash $Remote/deploy/install.sh"

Write-Host "==> Done"
