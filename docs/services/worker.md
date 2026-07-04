# Worker

**Сеть:** `network_mode: host`  
**Стек:** Python asyncio + NATS

## Назначение

Фоновый обработчик событий из NATS JetStream: уведомления в Telegram, напоминания за 24 часа, синхронизация с CRM mock.

## Подписки NATS

| Subject | Действие |
|---------|----------|
| `appointments.created` | Уведомление пациенту и staff-группе |
| `appointments.cancelled` | Уведомление об отмене |
| `appointments.rescheduled.*` | Уведомление о переносе |
| `reminders.scan` | Сканирование записей через 24 часа |
| `crm.appointment.sync_requested` | Синхронизация с crm-mock |

## Напоминания

Периодически (или по событию `reminders.scan`) worker запрашивает:

```
GET /api/reminders/due
```

и отправляет пациентам напоминания о записи на завтра.

## Telegram

Использует `shared/telegram_client.py` с поддержкой `TELEGRAM_PROXY_URL` — так же, как bot-gateway.

## Конфигурация

| Переменная | Назначение |
|------------|------------|
| `STAFF_GROUP_CHAT_ID` | Chat ID группы персонала |
| `TELEGRAM_BOT_TOKEN` | Токен для отправки сообщений |
| `CORE_API_URL` | `http://127.0.0.1:8100` |
| `NATS_URL` | `nats://127.0.0.1:4224` |

## Запуск

```bash
docker compose up worker
```

или в составе полного стека:

```bash
docker compose up --build
```
