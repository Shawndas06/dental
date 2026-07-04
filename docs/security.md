# Безопасность

## Webhook

Эндпоинт `POST /api/telegram/webhook` защищён:

1. **Secret token** — заголовок `X-Telegram-Bot-Api-Secret-Token` сверяется с `TELEGRAM_WEBHOOK_SECRET`.
2. **Rate limiting** — sliding window 60 запросов/минуту на IP (Redis).

Регистрация webhook с secret:

```python
await bot.set_webhook(url, secret_token=settings.telegram_webhook_secret)
```

## Callback data

- Максимум 64 символа.
- Без PII (телефон, email).
- Только разрешённые namespace (`shared/callbacks.py`).

## Idempotency

Все критичные мутации (`POST` записи, отмена, перенос) требуют заголовок `Idempotency-Key`. Повтор с тем же ключом возвращает тот же результат без дубликата.

## RBAC

Врачебные и staff-операции проверяют:

- заголовок `X-Role` (`doctor`, `staff`);
- списки `DOCTOR_TELEGRAM_IDS`, `STAFF_TELEGRAM_IDS`.

Реализация: `shared/security.py` → `require_permission`.

## Слоты и гонки

При одновременном бронировании одного слота второй запрос получает **HTTP 409**. Слот блокируется на уровне Core API.

## AI Safety

Перед показом пациенту ответ AI проходит валидацию (`services/ai_orchestrator/safety.py`):

| Проверка | Описание |
|----------|----------|
| Нет диагноза | Отказ на клинические вопросы |
| Реальные слоты | `callback_data` только с существующими `slot_id` |
| Нет галлюцинаций | Услуги только из clinic profile |

## Аудит

Критичные действия записываются в `audit_events` и публикуют `audit.events` в NATS.

```bash
curl http://127.0.0.1:8100/api/audit
```

## Секреты и PII

- `.env` не в репозитории.
- Логи не должны содержать полные токены и телефоны.
- Маскирование PII в audit при необходимости — `shared/security.py`.

## Рекомендации для production

- [ ] HTTPS для webhook
- [ ] Сильный `TELEGRAM_WEBHOOK_SECRET` (32+ символов)
- [ ] Ограничить доступ к `/debug/*` endpoints
- [ ] Ротация токена бота при утечке
- [ ] Firewall: только Telegram IP к webhook (опционально)
- [ ] Регулярные бэкапы PostgreSQL
