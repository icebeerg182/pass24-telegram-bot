# Архитектура

## Поток заказа пропуска

```
Пользователь Telegram
    │  "мерс А121МР777"
    ▼
bot/parser.py + bot/brands.py
    │  Mercedes-Benz, А121МР777
    ▼
pass24_api_client.Pass24ApiClient
    │  JWT в теле запроса (как в мобильном приложении)
    ▼
mobile-api.pass24online.ru/v1/passes
```

## Авторизация

1. `POST auth/login` с `phone` и `password` из `.env`
2. Токен (JWT) кладётся в поле `token` каждого запроса
3. Перед запросом проверяется `exp` в JWT; при 401 — повторный login
4. Креды хранятся только в `.env` на сервере

## Выбор адреса

При нескольких адресах в аккаунте выбирается первый, в `name` которого есть подстрока `PASS24_ADDRESS_KEYWORD` (регистронезависимо).

## Словарь марок

`bot/brands.py` — статические алиасы (`мерс` → `Mercedes-Benz`).

Затем имя сопоставляется со справочником `GET /v1/vehicle-models` (точные имена PASS24).

При необходимости дополняйте `BRAND_ALIASES`.

## Отличие от alpha.pass24.online

| | Mobile API (житель) | alpha.pass24.online (УК) |
|---|---|---|
| URL | `mobile-api.pass24online.ru/v1/` | `*.pass24.online/api/` |
| Логин | `phone` | `email` |
| Кто использует | Приложение PASS24.online | Админка / интеграции УК |

Бот использует **mobile API**, как мобильное приложение жителя.
