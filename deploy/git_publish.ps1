$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

Write-Host "==> git status"
git status

Write-Host "`n==> git add"
git add -A
if (Test-Path .env) {
    git restore --staged .env
    Write-Host "(.env не в коммите)"
}

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "`nНечего коммитить — возможно уже опубликовано."
    git status
    exit 0
}

Write-Host "`n==> commit"
git commit -m "Instant pass creation and admin public access" `
  -m "- Create passes instantly without confirmation" `
  -m "- Flexible plate/brand parsing: any order, colors ignored, multiline" `
  -m "- Admin temporary public access via /open 12|24|48 and /close" `
  -m "- Improved brand aliases and vehicle type handling"

Write-Host "`nCommit: $(git rev-parse --short HEAD)"

Write-Host "`n==> push"
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "HTTPS failed, trying SSH..."
    git remote set-url origin git@github.com:icebeerg182/pass24-telegram-bot.git
    git push origin main
}

Write-Host "`n==> done"
git status
