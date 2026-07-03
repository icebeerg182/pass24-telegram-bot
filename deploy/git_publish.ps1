$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$version = (Get-Content VERSION -Raw).Trim()

git add -A
if (Test-Path .env) { git restore --staged .env }

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "Nothing to commit"
    exit 0
}

git commit -m "Update v$version"
git push origin main

if ($LASTEXITCODE -ne 0) {
    Write-Error "git push failed. Configure origin: git remote set-url origin git@github.com:YOUR_USER/pass24-telegram-bot.git"
}

Write-Host "Done"
