# Деплой

## Локальная разработка

Рекомендуемый режим: **polling** + прокси для Telegram API.

```bash
docker compose up --build
```

## Production checklist

| Шаг | Действие |
|-----|----------|
| 1 | Заполнить `.env` production-секретами |
| 2 | `TELEGRAM_MODE=webhook` |
| 3 | HTTPS URL для `TELEGRAM_WEBHOOK_URL` |
| 4 | Настроить `STAFF_GROUP_CHAT_ID` |
| 5 | `AI_MODE=rules` или настроить OpenAI |
| 6 | Бэкапы PostgreSQL |
| 7 | Мониторинг health endpoints |

## Webhook

URL должен указывать на bot-gateway:

```
https://your-domain.example.com/api/telegram/webhook
```

Авторегистрация при старте `bot-gateway`. Ручная регистрация:

```bash
docker compose exec bot-gateway python -m scripts.set_webhook
```

## ngrok (альтернатива)

```bash
ngrok http 8180
```

```env
TELEGRAM_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://xxxx.ngrok-free.app/api/telegram/webhook
```

!!! warning "ERR_NGROK_9040"
    ngrok может блокировать IP региона. В этом случае используйте polling, Cloudflare Tunnel или VPS с публичным IP.

## Порты

По умолчанию порты смещены для совместимости с другими Docker-проектами:

| Сервис | Хост |
|--------|------|
| bot-gateway | 8180 |
| core-api | 8100 |
| postgres | 55432 |

При деплое на VPS можно вернуть стандартные порты через `.env`.

## Сборка Docker

```bash
docker compose build --no-cache
docker compose up -d
```

При ошибках DNS при сборке в `docker-compose.yml` включён `build.network: host`. При необходимости добавьте DNS в `/etc/docker/daemon.json`:

```json
{
  "dns": ["8.8.8.8", "1.1.1.1"]
}
```

## Health checks

```bash
curl http://127.0.0.1:8180/health
curl http://127.0.0.1:8100/health
curl http://127.0.0.1:8101/health
```

## Публикация документации

```bash
pip install -e ".[docs]"
mkdocs build
```

Папка `site/` — статический сайт. Варианты хостинга:

- **GitHub Pages** — `mkdocs gh-deploy`
- **Netlify / Vercel** — deploy папки `site/`
- **Nginx** — `root /path/to/site`

## Масштабирование (post-MVP)

- bot-gateway: горизонтально за load balancer (webhook mode)
- core-api: несколько реплик + один PostgreSQL
- worker: несколько consumers в одной NATS consumer group
- Redis: managed instance для rate limit
