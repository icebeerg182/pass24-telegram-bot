$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))

$version = (Get-Content VERSION -Raw).Trim()
Write-Host "==> Fresh publish v$version (single commit, force push)"

if (Test-Path .env) {
    Write-Host "NOTE: .env is gitignored and will not be committed"
}

# New branch without history
git checkout --orphan fresh-main

git add -A

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "ERROR: nothing staged for commit"
    exit 1
}

git commit -m "PASS24 Telegram Bot v$version (Docker)"

# Rename orphan branch to main (do not delete main while checked out)
git branch -M main
git tag -f "v$version"

Write-Host ""
Write-Host "==> Force push to GitHub"
git push -f origin main
if ($LASTEXITCODE -ne 0) {
    Write-Error "git push failed. Configure origin: git remote set-url origin git@github.com:YOUR_USER/pass24-telegram-bot.git"
    exit 1
}

git push -f origin "v$version"

Write-Host ""
Write-Host "Done. GitHub has a single commit for v$version"
