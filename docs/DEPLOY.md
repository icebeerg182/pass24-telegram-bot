# Деплой

Запуск только через **Docker**.

| Документ | Для кого |
|---|---|
| [SERVER_INSTALL.md](SERVER_INSTALL.md) | Установка на сервер с нуля |
| [DOCKER.md](DOCKER.md) | Команды Docker |
| [GITHUB.md](GITHUB.md) | Публикация на GitHub |

## На сервере (кратко)

```bash
rm -rf /opt/pass24-telegram-bot
git clone git@github.com:icebeerg182/pass24-telegram-bot.git /opt/pass24-telegram-bot
cd /opt/pass24-telegram-bot
cp /root/pass24.env.backup .env   # ваш сохранённый .env
mkdir -p data
docker compose up -d --build
```

Подробно: [SERVER_INSTALL.md](SERVER_INSTALL.md)
