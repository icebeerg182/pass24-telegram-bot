# Публикация на GitHub

Репозиторий: `https://github.com/YOUR_GITHUB_USER/pass24-telegram-bot`
Версия: **0.0.1** (файл `VERSION`)

---

## Обычное обновление

```powershell
cd path\to\pass24-telegram-bot
git add .
git commit -m "описание изменений"
git push origin main
```

Или:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\git_publish.ps1
```

---

## Чистая история (один коммит, только Docker-версия)

Выполнить **на ПК** в каталоге проекта:

```powershell
cd path\to\pass24-telegram-bot

# новая ветка без истории
git checkout --orphan fresh-main
git add -A
git restore --staged .env 2>$null

git commit -m "PASS24 Telegram Bot v0.0.1 (Docker)"

git branch -D main
git branch -m main

git tag -f v0.0.1

# заменить историю на GitHub
git push -f origin main
git push -f origin v0.0.1
```

После этого на GitHub останется **один коммит** с текущим кодом.

> ⚠️ `git push -f` перезаписывает историю. Для private-репозитория это безопасно, если работаете один.

---

## Теги версий

```powershell
git tag -a v0.0.2 -m "Version 0.0.2"
git push origin v0.0.2
```

Не забудьте обновить `VERSION` и `CHANGELOG.md`.

---

## Не коммитить

- `.env`
- `data/allowed_users.json`
- `.venv/`
