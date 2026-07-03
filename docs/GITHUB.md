# Публикация на GitHub

Репозиторий: https://github.com/icebeerg182/pass24-telegram-bot (private)

Текущая версия: **0.0.1** (`VERSION`)

---

## Первый раз (уже сделано)

```bash
git clone git@github.com:icebeerg182/pass24-telegram-bot.git
```

---

## Обычное обновление (Windows)

```powershell
cd C:\Users\icebeerg\Projects\pass24-telegram-bot

git status
git add .
git status

# .env не должен попасть в коммит (в .gitignore)
git commit -m "Release 0.0.1: Docker deployment"

git push origin main
```

Или скрипт:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\git_publish.ps1
```

Если push по HTTPS не работает:

```powershell
git remote set-url origin git@github.com:icebeerg182/pass24-telegram-bot.git
git push origin main
```

---

## Тег версии (рекомендуется для релизов)

```powershell
cd C:\Users\icebeerg\Projects\pass24-telegram-bot

git tag -a v0.0.1 -m "Version 0.0.1"
git push origin v0.0.1
```

---

## Следующие версии

1. Изменить число в файле `VERSION` (например `0.0.2`)
2. Добавить запись в `CHANGELOG.md`
3. Обновить тег образа в `docker-compose.yml` (строка `image:`)
4. Коммит + push + тег `v0.0.2`

```powershell
git add VERSION CHANGELOG.md docker-compose.yml
git commit -m "Release 0.0.2"
git tag -a v0.0.2 -m "Version 0.0.2"
git push origin main
git push origin v0.0.2
```

---

## Что не коммитить

- `.env` — токены и пароли
- `data/allowed_users.json` — список пользователей с сервера
- `.venv/`

---

## Проверка после push

Откройте https://github.com/icebeerg182/pass24-telegram-bot — должны быть:

- `Dockerfile`, `docker-compose.yml`
- `VERSION` = `0.0.1`
- `CHANGELOG.md`
- `docs/MIGRATE_TO_DOCKER.md`
