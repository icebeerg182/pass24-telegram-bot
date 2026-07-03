# Работа с проектом в Cursor

## Как «дать доступ» ассистенту

Отдельного доступа к GitHub для ИИ не нужно. Достаточно **открыть папку проекта в Cursor**:

### Windows / Mac

```bash
git clone git@github.com:YOUR_GITHUB_USER/pass24-telegram-bot.git
cd pass24-telegram-bot
cp .env.example .env
# заполнить .env
```

В Cursor: **File → Open Folder** → выбрать `pass24-telegram-bot`.

После этого ассистент видит код, README и может править файлы.

### Секреты

- `.env` **не в GitHub** — создайте локально на каждом устройстве
- На сервере: `/opt/pass24-telegram-bot/.env`

### Обновление кода

```bash
git pull
# на сервере: python deploy/remote_deploy.py
```

## Приватный репозиторий

Репозиторий private — видите только вы (и collaborators, если добавите).

SSH clone (рекомендуется):

```bash
git clone git@github.com:YOUR_GITHUB_USER/pass24-telegram-bot.git
```

## Collaborator (если нужен другому человеку)

GitHub → Settings → Collaborators → Add people.

Для Cursor на вашем ПК collaborator **не нужен**.
