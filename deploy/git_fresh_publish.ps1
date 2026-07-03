$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$version = (Get-Content VERSION -Raw).Trim()
Write-Host "==> Fresh publish v$version (single commit, force push)"

if (Test-Path .env) { Write-Host "WARNING: .env exists — will NOT be committed" }

git checkout --orphan fresh-main 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Already on orphan or error — continuing with add/commit"
}

git add -A
if (Test-Path .env) { git restore --staged .env }

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "Nothing to commit"
    exit 1
}

git commit -m "PASS24 Telegram Bot v$version (Docker)"

git branch -D main 2>$null
git branch -m main
git tag -f "v$version"

Write-Host "`n==> Force push to GitHub"
git push -f origin main
git push -f origin "v$version"

if ($LASTEXITCODE -ne 0) {
    Write-Host "HTTPS failed, trying SSH..."
    git remote set-url origin git@github.com:icebeerg182/pass24-telegram-bot.git
    git push -f origin main
    git push -f origin "v$version"
}

Write-Host "`nDone. GitHub now has a single commit for v$version"
