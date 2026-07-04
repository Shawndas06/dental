# Dental Telegram Bot MVP

Гибридный Telegram-бот стоматологической клиники по ТЗ:

- пациент может начать с кнопок или свободной фразы;
- AI используется только для первичной маршрутизации;
- запись, перенос, отмена и подтверждение выполняются только кнопками;
- цены, врачи, услуги и слоты берутся из данных клиники;
- клинические вопросы получают безопасный отказ;
- ключевые события публикуются в NATS JetStream;
- запуск выполняется через Docker Compose.

## Быстрый запуск

```bash
cp .env.example .env
```

Заполните в `.env`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_WEBHOOK_URL`
- `STAFF_GROUP_CHAT_ID` при необходимости уведомлений в группу

Если `api.telegram.org` недоступен напрямую (типично без VPN), укажите локальный прокси v2rayA/clash:

```env
TELEGRAM_PROXY_URL=http://127.0.0.1:20170
TELEGRAM_MODE=polling
```

Проверка с ноутбука:

```bash
curl -x http://127.0.0.1:20170 "https://api.telegram.org/bot<TOKEN>/getMe"
```

`bot-gateway` и `worker` запускаются с `network_mode: host`, чтобы видеть прокси на `127.0.0.1`.

Для запуска на ноутбуке без ngrok используйте long polling:

```env
TELEGRAM_MODE=polling
```

Для production или когда есть публичный URL:

```env
TELEGRAM_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app/api/telegram/webhook
```

Для webhook через ngrok:

```bash
ngrok http 8180
```

После этого укажите:

```env
TELEGRAM_WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app/api/telegram/webhook
```

Порты по умолчанию смещены, чтобы не конфликтовать с другими Docker-проектами на ноутбуке:

| Сервис | Хост-порт |
|--------|-----------|
| bot-gateway | 8180 |
| core-api | 8100 |
| ai-orchestrator | 8101 |
| crm-mock | 8102 |
| admin | 8190 |
| postgres | 55432 |
| redis | 6380 |
| nats | 4224 |

## Специфика клиники

Перед настройкой под реальную клинику заполните **[STOMATOLOGY_CLINIC_SPEC.md](STOMATOLOGY_CLINIC_SPEC.md)** — анкета с врачами, услугами, правилами маршрутизации AI и чеклистом приёмки.

Запуск:

```bash
docker compose up --build
```

Если сборка падает с `Temporary failure resolving` при `apt-get` или `pip install`, это проблема DNS внутри Docker BuildKit. В `docker-compose.yml` для сборки уже включён `network: host`. Если ошибка останется, добавьте DNS в Docker:

```json
{
  "dns": ["8.8.8.8", "1.1.1.1"]
}
```

в `/etc/docker/daemon.json`, затем `sudo systemctl restart docker`.

Webhook регистрируется автоматически при старте `bot-gateway`, если заполнены `TELEGRAM_BOT_TOKEN` и `TELEGRAM_WEBHOOK_URL`. Также можно выполнить вручную:

```bash
docker compose exec bot-gateway python -m scripts.set_webhook
```

## Сервисы

- `bot-gateway` — Telegram webhook, кнопочные сценарии, текстовый intake.
- `core-api` — пользователи, пациенты, врачи, услуги, слоты, записи, переносы, уведомления, аудит.
- `ai-orchestrator` — CKS, conversational intake, safe refusal, no hallucination checks.
- `crm-mock` — mock CRM/SRM для primary/repeat lookup и sync.
- `worker` — NATS consumers, уведомления, staff group, напоминания за 24 часа.
- `postgres`, `redis`, `nats` — инфраструктура.

## Демо-сценарии

1. Пациент пишет: `Болит зуб слева уже неделю`.
2. Бот показывает направление и реальные слоты.
3. Пациент нажимает слот.
4. Запись создаётся, публикуется `appointments.created`, worker создаёт уведомление.

Граничные сценарии:

- `Что у меня за болезнь?` → безопасный отказ без диагноза.
- `Хочу имплантацию` → отказ, если услуги нет в профиле клиники.
- Перенос через `Мои записи` → кнопочный сценарий без AI.

## Проверка без Telegram

Можно отправлять update напрямую в debug endpoint:

```bash
curl -X POST http://localhost:8080/debug/simulate \
  -H 'Content-Type: application/json' \
  -d '{"message":{"chat":{"id":1001},"from":{"id":1001,"username":"demo"},"text":"/start"}}'
```

## Тесты

Локально:

```bash
pip install -e ".[test]"
pytest -v
```

В контейнере:

```bash
docker compose run --rm core-api pytest -v
```

## Документация (MkDocs)

Сайт документации в папке `docs/`:

```bash
pip install -e ".[docs]"
mkdocs serve
```

Откройте `http://127.0.0.1:8000`. Сборка статики:

```bash
mkdocs build
```

Результат — папка `site/`.

## Админ-панель

```bash
# В .env задайте ADMIN_TOKEN
docker compose up -d admin core-api bot-gateway ai-orchestrator
```

Откройте `http://127.0.0.1:8190`, войдите с `ADMIN_TOKEN`.

Раздел **Демо-сценарий** — автоматическая проверка регистрации, AI intake, записи и граничных случаев.

CLI:

```bash
python -m scripts.run_demo_scenario
```

## Безопасность

- Webhook проверяет `X-Telegram-Bot-Api-Secret-Token`.
- `callback_data` не содержит телефон, username или другие персональные данные.
- Все критичные действия используют idempotency key.
- Запись на занятый слот возвращает `409`.
- Роли проверяются на backend для врачебных и staff-сценариев.
- AI-вывод валидируется перед показом пациенту.
- `.env.example` не содержит реальных секретов.
