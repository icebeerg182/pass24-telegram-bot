$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$version = (Get-Content VERSION -Raw).Trim()
Write-Host "==> Publish version $version"

Write-Host "`n==> git status"
git status

Write-Host "`n==> git add"
git add -A
if (Test-Path .env) {
    git restore --staged .env
    Write-Host "(.env не в коммите)"
}

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "`nНечего коммитить."
    exit 0
}

Write-Host "`n==> commit"
git commit -m "Release $version: Docker deployment" `
  -m "- Docker image and docker-compose" `
  -m "- Migration docs from systemd to Docker" `
  -m "- GitHub publish guide and CHANGELOG"

Write-Host "`nCommit: $(git rev-parse --short HEAD)"

Write-Host "`n==> tag v$version (if missing)"
$tagExists = git tag -l "v$version"
if (-not $tagExists) {
    git tag -a "v$version" -m "Version $version"
}

Write-Host "`n==> push"
git push origin main
git push origin "v$version" 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "Trying SSH remote..."
    git remote set-url origin git@github.com:icebeerg182/pass24-telegram-bot.git
    git push origin main
    git push origin "v$version"
}

Write-Host "`n==> done"
git status
