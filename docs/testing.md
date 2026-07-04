# Тестирование

## Запуск

```bash
pip install -e ".[test]"
pytest -v
```

В Docker:

```bash
docker compose run --rm core-api pytest -v
```

Конфигурация: `pyproject.toml` → `[tool.pytest.ini_options]`.

## Структура тестов

```
tests/
  unit/           # callbacks, CKS, security, validator
  integration/    # Core API
  e2e/            # Демо-сценарии бота и AI
```

## Unit-тесты

| Файл | Что проверяет |
|------|---------------|
| `test_callbacks.py` | Парсинг callback, запрет PII |
| `test_cks_and_safety.py` | Классификация, валидатор AI |
| `test_security.py` | Webhook secret, rate limit |

## E2E-сценарии

| Тест | Сценарий |
|------|----------|
| `test_text_intake_shows_real_slot_buttons` | Текст → слоты терапевта |
| `test_clinical_question_safe_refusal` | Отказ от диагноза |
| `test_unknown_service_no_hallucination` | Нет имплантации в клинике |
| `test_button_pricing_flow_does_not_call_ai` | Цены без вызова AI |

## Проверка без Telegram

```bash
curl -X POST http://127.0.0.1:8180/debug/simulate \
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

- [ ] `pytest` проходит локально
- [ ] `docker compose up --build` поднимает все health checks
- [ ] `/start` → регистрация → запись в Telegram
- [ ] Текстовый intake показывает реальные слоты
