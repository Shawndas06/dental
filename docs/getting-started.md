# Быстрый старт

## Требования

- Docker и Docker Compose
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- При блокировке `api.telegram.org` — локальный прокси (v2rayA, Clash и т.п.)

## 1. Настройка окружения

```bash
cp .env.example .env
```

Минимально заполните:

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен бота |
| `TELEGRAM_WEBHOOK_SECRET` | Случайная строка для проверки webhook |
| `TELEGRAM_PROXY_URL` | Прокси, если Telegram API недоступен напрямую |

Пример для локальной разработки с v2rayA:

```env
TELEGRAM_MODE=polling
TELEGRAM_PROXY_URL=http://127.0.0.1:20170
```

Проверка доступа к Telegram API:

```bash
curl -x http://127.0.0.1:20170 "https://api.telegram.org/bot<TOKEN>/getMe"
```

## 2. Запуск

```bash
docker compose up -d --build
```

Документация для ментора (MkDocs):

```bash
docker compose up -d docs
# или: mkdocs serve -a 0.0.0.0:8008
```

См. также [Руководство для ментора](mentor-guide.md).

Сервисы поднимаются с портами, смещёнными относительно стандартных (чтобы не конфликтовать с другими проектами):

| Сервис | URL на хосте |
|--------|--------------|
| **документация (MkDocs)** | `http://127.0.0.1:8008` |
| **админ-панель** | `http://127.0.0.1:8190` |
| bot-gateway | `http://127.0.0.1:8180` |
| core-api | `http://127.0.0.1:8100` |
| ai-orchestrator | `http://127.0.0.1:8101` |
| crm-mock | `http://127.0.0.1:8102` |
| postgres | `127.0.0.1:55432` |
| redis | `127.0.0.1:6380` |
| nats | `127.0.0.1:4224` |

Проверка здоровья:

```bash
curl http://127.0.0.1:8180/health
```

## 3. Режимы Telegram

### Polling (рекомендуется локально)

Не нужен публичный URL. Бот сам опрашивает Telegram API.

```env
TELEGRAM_MODE=polling
```

`bot-gateway` и `worker` используют `network_mode: host`, чтобы видеть прокси на `127.0.0.1`.

### Webhook (production)

Нужен HTTPS-URL, доступный из интернета:

```env
TELEGRAM_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://your-domain.example.com/api/telegram/webhook
```

Webhook регистрируется автоматически при старте `bot-gateway`. Вручную:

```bash
docker compose exec bot-gateway python -m scripts.set_webhook
```

!!! note "ngrok"
    Если ngrok блокирует ваш IP (`ERR_NGROK_9040`), используйте polling или другой туннель (Cloudflare Tunnel и т.п.).

## 4. Первый запуск в Telegram

1. Откройте бота в Telegram.
2. Отправьте `/start`.
3. Нажмите **Продолжить** для быстрой регистрации.
4. Выберите **Записаться** или напишите, например: `Болит зуб слева уже неделю`.

## 5. Отладка без Telegram

Debug-эндпоинт симулирует update:

```bash
curl -X POST http://127.0.0.1:8180/debug/simulate \
  -H "X-Debug-Token: $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"message":{"chat":{"id":1001},"from":{"id":1001,"first_name":"Demo","username":"demo"},"text":"/start"}}'
```

Требуется `DEBUG_API_ENABLED=true` в `.env`.

## 6. Тесты

```bash
pip install -e ".[test]"
pytest -v
```

Подробнее: [Тестирование](testing.md).
