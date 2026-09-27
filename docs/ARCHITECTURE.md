# Архитектура

## Поток заказа пропуска

```
Пользователь Telegram
    │  "мерс А121МР777"  /  ссылка Яндекс Доставки  /  текст Wheely
    ▼
bot/parser.py + bot/brands.py
    │  номер (regex) + марка (алиасы / fuzzy)
    │  если марка не найдена и BOT_LLM_BRAND_RESOLVER=true
    ▼
bot/llm_brand.py  (Groq)  → сверка со справочником PASS24
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

Опционально: кнопка «📍 Адрес» (`BOT_ENABLE_ADDRESS_PICKER`).

## Госномер

`BOT_REQUIRE_FULL_PLATE` (по умолчанию `true`):

| Режим | Что принимается | Пример |
|---|---|---|
| `true` | полный госномер с регионом | `А121МР77` |
| `false` | цифры (внутренний номер), короткий или полный госномер | `Mazda 100`, `А121МР`, `А121МР77` |

Спрашивается при первой установке (`deploy/install.sh`).

## Словарь марок и LLM

`bot/brands.py` — статические алиасы (`мерс` → `Mercedes-Benz`, `маруся` → `Marussia`).

Имя сопоставляется со справочником `GET /v1/vehicle-models`.

Если не найдено и включён `BOT_LLM_BRAND_RESOLVER`, вызывается Groq (`bot/llm_brand.py`): модель выбирает марку **только из каталога**, ответ кэшируется в `data/brands_learned.json`.

## Яндекс Доставка

Ссылка `https://dostavka.yandex.ru/route/#<uuid>` → публичный `shared-route/info` → `vehicle_model` / `vehicle_number`.

## Отличие от alpha.pass24.online

| | Mobile API (житель) | alpha.pass24.online (УК) |
|---|---|---|
| URL | `mobile-api.pass24online.ru/v1/` | `*.pass24.online/api/` |
| Логин | `phone` | `email` |
| Кто использует | Приложение PASS24.online | Админка / интеграции УК |

Бот использует **mobile API**, как мобильное приложение жителя.

Клиент `pass24_api_client/` основан на [dmtrbrlkv/pass24](https://github.com/dmtrbrlkv/pass24).
