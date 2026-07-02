# Создать приватный репозиторий на GitHub и запушить код
# Требуется: gh auth login
# Запуск: .\deploy\setup-github.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))

if (-not (Test-Path .git)) { git init }

$staged = git status --porcelain .env 2>$null
if ($staged -match "^A\s+\.env" -or $staged -match "^\?\?\s+\.env") {
    if (-not (Select-String -Path .gitignore -Pattern '\.env' -Quiet)) {
        Add-Content .gitignore "`n.env"
    }
}

git add -A
Write-Host "=== Staged files ( .env must NOT be here ) ==="
git status

if (git diff --cached --name-only | Select-String -Pattern '^\.env$' -Quiet) {
    Write-Error ".env is staged! Aborting. Check .gitignore"
}

$hasHead = $false
git rev-parse --verify HEAD 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { $hasHead = $true }

$stagedFiles = git diff --cached --name-only
if ($stagedFiles) {
    if (-not $hasHead) {
        git commit -m @"
Add PASS24 Telegram bot for resident pass ordering

Based on dmtrbrlkv/pass24 mobile API client. Brand parser, Renessans
address filter, JWT refresh, deploy scripts and documentation.
"@
    } else {
        git commit -m "Update PASS24 Telegram bot"
    }
} else {
    Write-Host "Nothing to commit."
}

gh auth status
$repoName = "pass24-telegram-bot"
try {
    gh repo create $repoName --private --source=. --remote=origin --push `
        --description "Telegram bot for PASS24.online resident vehicle passes"
} catch {
    Write-Host "Retrying with suffix..."
    gh repo create "${repoName}-private" --private --source=. --remote=origin --push `
        --description "Telegram bot for PASS24.online resident vehicle passes"
}

gh repo view --web 2>$null
Write-Host "Done. Repo URL:"
gh repo view --json url -q .url
