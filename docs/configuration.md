# Конфигурация

Все настройки загружаются из `.env` через `shared/config.py` (pydantic-settings).

## Telegram

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TELEGRAM_BOT_TOKEN` | — | Токен бота (обязательно) |
| `TELEGRAM_MODE` | `polling` | `polling` или `webhook` |
| `TELEGRAM_WEBHOOK_URL` | — | URL webhook (для webhook-режима) |
| `TELEGRAM_WEBHOOK_SECRET` | — | Secret token для заголовка |
| `TELEGRAM_PROXY_URL` | — | HTTP/SOCKS прокси для api.telegram.org |
| `TELEGRAM_API_BASE` | `https://api.telegram.org` | Base URL API |

## Сервисы

| Переменная | Описание |
|------------|----------|
| `CORE_API_URL` | URL Core API (в Docker: `http://core-api:8000`, host: `http://127.0.0.1:8100`) |
| `AI_ORCHESTRATOR_URL` | URL AI Orchestrator |
| `CRM_MOCK_URL` | URL CRM mock |
| `BOT_GATEWAY_PORT` | Порт bot-gateway на хосте (8180) |

## База данных

| Переменная | Описание |
|------------|----------|
| `DATABASE_URL` | PostgreSQL connection string |
| `POSTGRES_DB` | Имя БД |
| `POSTGRES_USER` | Пользователь |
| `POSTGRES_PASSWORD` | Пароль |
| `POSTGRES_PORT` | Порт на хосте (55432) |

## Инфраструктура

| Переменная | Описание |
|------------|----------|
| `REDIS_URL` | Redis для rate limit |
| `NATS_URL` | NATS JetStream |
| `LOG_LEVEL` | `INFO`, `DEBUG`, … |

## Клиника и роли

| Переменная | Описание |
|------------|----------|
| `CLINIC_PHONE` | Телефон в экране контактов |
| `STAFF_GROUP_CHAT_ID` | Chat ID группы персонала |
| `DOCTOR_TELEGRAM_IDS` | Telegram ID врачей (через запятую) |
| `STAFF_TELEGRAM_IDS` | Telegram ID staff |

## AI

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `AI_MODE` | `rules` | `rules` или `openai` |
| `OPENAI_API_KEY` | — | Ключ OpenAI |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Base URL |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Модель |

## CRM Mock

| Переменная | Описание |
|------------|----------|
| `CRM_MOCK_FAILURE_RATE` | Вероятность сбоя (0–1) для тестов |

## Пример `.env` для локальной разработки

```env
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_MODE=polling
TELEGRAM_PROXY_URL=http://127.0.0.1:20170
TELEGRAM_WEBHOOK_SECRET=random-secret-string
CLINIC_PHONE=+79990000000
AI_MODE=rules
```

!!! danger "Секреты"
    Не коммитьте `.env` в git. Используйте `.env.example` как шаблон.

## Docker Compose overrides

`bot-gateway` и `worker` в compose переопределяют:

```yaml
CORE_API_URL: http://127.0.0.1:8100
TELEGRAM_PROXY_URL: http://127.0.0.1:20170
```

из-за `network_mode: host`.
