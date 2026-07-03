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
    git remote set-url origin git@github.com:icebeerg182/pass24-telegram-bot.git
    git push origin main
}

Write-Host "Done"
