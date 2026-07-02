# Создать приватный репозиторий на GitHub и запушить код
# Требуется: git, gh auth login
# Запуск: .\deploy\setup-github.ps1

Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))

if (-not (Test-Path .git)) { git init }

if (-not (Select-String -Path .gitignore -Pattern '\.env' -Quiet)) {
    Add-Content .gitignore "`n.env"
}

git add -A
Write-Host "=== Staged files (.env must NOT be listed) ==="
git status

$staged = @(git diff --cached --name-only 2>$null)
if ($staged -contains ".env") {
    Write-Host "ERROR: .env is staged! Remove it: git rm --cached .env" -ForegroundColor Red
    exit 1
}

if ($staged.Count -gt 0) {
    git commit -m "Add PASS24 Telegram bot for resident pass ordering"
    Write-Host "Committed $($staged.Count) files."
} else {
    Write-Host "Nothing new to commit."
}

gh auth status
if ($LASTEXITCODE -ne 0) { exit 1 }

$repoName = "pass24-telegram-bot"
$hasRemote = git remote get-url origin 2>$null
if (-not $hasRemote) {
    gh repo create $repoName --private --source=. --remote=origin --push `
        --description "Telegram bot for PASS24.online resident vehicle passes"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Retrying with another name..."
        gh repo create "${repoName}-private" --private --source=. --remote=origin --push `
            --description "Telegram bot for PASS24.online resident vehicle passes"
    }
} else {
    git branch -M main 2>$null
    git push -u origin main
    if ($LASTEXITCODE -ne 0) { git push -u origin master }
}

Write-Host "Done. Repo URL:"
gh repo view --json url -q .url
