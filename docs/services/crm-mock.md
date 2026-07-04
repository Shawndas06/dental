# CRM Mock

**Порт:** `8102`  
**Стек:** FastAPI

## Назначение

Имитация внешней CRM/SRM для демо и интеграционных тестов. Core API вызывает mock при lookup пациента и sync записей.

## Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Health check |
| POST | `/crm/patients/lookup` | Поиск пациента (primary/repeat) |
| GET | `/crm/doctors` | Список врачей |
| GET | `/crm/services` | Услуги CRM |
| POST | `/crm/appointments/sync` | Синхронизация записи |

## Поведение lookup

- Для новых `telegram_user_id` возвращает `exists: false` (первичный визит).
- Для известных ID — `exists: true`, `crmPatientId`, имя из mock-базы.

## Отказоустойчивость

Переменная `CRM_MOCK_FAILURE_RATE` (0–1) позволяет симулировать сбои CRM для тестов.

При сбое Core API публикует `crm.appointment.sync_failed`, worker может повторить попытку.
