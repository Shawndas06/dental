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

## Безопасность и сервисы

| Переменная | Описание |
|------------|----------|
| `INTERNAL_SERVICE_TOKEN` | Общий секрет для `X-Service-Token` между сервисами |
| `ADMIN_TOKEN` | Вход в админку и `X-Admin-Token` |
| `ADMIN_SESSION_TTL_HOURS` | TTL сессии админки (по умолчанию 24) |
| `DEBUG_API_ENABLED` | `true` — включить `/debug/*` |
| `DEBUG_API_TOKEN` | Токен для `X-Debug-Token` (если пуст — используется `ADMIN_TOKEN`) |
| `NOTIFY_TELEGRAM_USERNAME` | Username для уведомления о готовности (без `@`) |

## Сервисы

| Переменная | Описание |
|------------|----------|
| `CORE_API_URL` | URL Core API (в Docker: `http://core-api:8000`, host: `http://127.0.0.1:8100`) |
| `AI_ORCHESTRATOR_URL` | URL AI Orchestrator |
| `CRM_MOCK_URL` | URL CRM mock |
| `BOT_GATEWAY_PORT` | Порт bot-gateway на хосте (8180) |
| `ADMIN_PORT` | Порт админки (8190) |
| `DOCS_PORT` | Порт MkDocs (8008) |

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
| `REDIS_URL` | Redis для rate limit и bot state |
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
| `AI_MODE` | `rules` | `rules` (локально) или `openai` |
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
TELEGRAM_PROXY_URL=http://127.0.0.1:20171
TELEGRAM_WEBHOOK_SECRET=random-secret-string
INTERNAL_SERVICE_TOKEN=random-internal-token-min-32-chars
ADMIN_TOKEN=your-admin-secret
DEBUG_API_ENABLED=true
CLINIC_PHONE=+79990000000
AI_MODE=rules
```

!!! danger "Секреты"
    Не коммитьте `.env` в git. Используйте `.env.example` как шаблон.

## Docker Compose overrides

`bot-gateway`, `worker` и `admin` в compose используют `network_mode: host`:

```yaml
CORE_API_URL: http://127.0.0.1:8100
TELEGRAM_PROXY_URL: http://127.0.0.1:20171
REDIS_URL: redis://127.0.0.1:6380
```

из-за доступа к локальному proxy на `127.0.0.1`.

Инфраструктурные порты привязаны к `127.0.0.1` на хосте (см. [Безопасность](security.md)).
