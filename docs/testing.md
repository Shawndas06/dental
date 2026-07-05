# Тестирование

## Запуск

```bash
pip install -e ".[test]"
pytest -v
```

Ожидаемый результат: **51 passed**.

В Docker:

```bash
docker compose run --rm core-api pytest -q
```

Конфигурация: `pyproject.toml` → `[tool.pytest.ini_options]`.  
Тесты используют SQLite in-memory (`tests/conftest.py`).

## Smoke-тест (живой стек)

После `docker compose up -d`:

```bash
source .env
python3 scripts/smoke_test.py
```

Проверяет health всех сервисов, регистрацию, AI intake, создание записи.

## Структура тестов

```
tests/
  unit/           # callbacks, CKS, security, patient proof, service auth
  integration/    # Core API
  e2e/            # Демо-сценарии бота и AI
```

## Unit-тесты

| Файл | Что проверяет |
|------|---------------|
| `test_callbacks.py` | Парсинг callback, запрет PII |
| `test_cks_and_safety.py` | Классификация, валидатор AI |
| `test_security.py` | Webhook secret, rate limit |
| `test_patient_proof.py` | HMAC patient proof |
| `test_service_auth.py` | Service token middleware |

## E2E-сценарии

| Тест | Сценарий |
|------|----------|
| `test_text_intake_shows_real_slot_buttons` | Текст → слоты терапевта |
| `test_clinical_question_safe_refusal` | Отказ от диагноза |
| `test_unknown_service_no_hallucination` | Нет имплантации в клинике |
| `test_button_pricing_flow_does_not_call_ai` | Цены без вызова AI |

## Проверка без Telegram

При `DEBUG_API_ENABLED=true`:

```bash
curl -X POST http://127.0.0.1:8180/debug/simulate \
  -H "X-Debug-Token: $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "callback_query": {
      "id": "1",
      "from": {"id": 1001, "username": "demo"},
      "message": {"chat": {"id": 1001}},
      "data": "pricing:list"
    }
  }'
```

## Покрытие (опционально)

```bash
pip install pytest-cov
pytest --cov=services --cov=shared
```

## CI checklist

- [ ] `pytest` — 51 passed
- [ ] `python3 scripts/smoke_test.py` — success
- [ ] `docker compose up --build` — все health checks green
- [ ] Админ → **Демо-сценарий** — все шаги OK
- [ ] `/start` → регистрация → запись в Telegram
