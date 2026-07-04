# Core API

**Порт:** `8100` (внутри контейнера `8000`)  
**Стек:** FastAPI + SQLAlchemy + PostgreSQL

## Назначение

Центральный сервис доменной логики: пользователи, пациенты, врачи, услуги, слоты, записи, переносы, уведомления, аудит.

## Основные сущности

| Сущность | Описание |
|----------|----------|
| `User` | Telegram-пользователь (chat_id, role) |
| `Patient` | Пациент клиники, связь с CRM |
| `Doctor` | Врач и специальность |
| `ClinicService` | Услуга с ценой и длительностью |
| `Slot` | Временной слот врача |
| `Appointment` | Запись на приём |
| `RescheduleRequest` | Запрос переноса (approval flow) |
| `AuditEvent` | Аудит критичных действий |

## Ключевые эндпоинты

Полный список: [API — обзор](../api/overview.md).

### Пациенты

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/patients/lookup` | Найти или создать пациента |
| GET | `/api/patients/by-telegram/{id}` | Пациент по Telegram ID |
| POST | `/api/patients/quick-register` | Быстрая регистрация |

### Расписание и записи

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/schedule/slots/available` | Свободные слоты |
| POST | `/api/appointments` | Создать запись |
| POST | `/api/appointments/{id}/cancel` | Отменить |
| POST | `/api/appointments/{id}/reschedule/by-patient` | Перенос пациентом |

### Справочники

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/services` | Услуги и цены |
| GET | `/api/doctors` | Врачи |
| GET | `/api/clinic-profile` | Профиль клиники |

## Idempotency

Критичные `POST` принимают заголовок `Idempotency-Key`. Повторный запрос с тем же ключом не создаёт дубликат.

Примеры ключей:

- `appointment-create:{telegram_user_id}:{slot_id}`
- `cancel:{appointment_id}`
- `reschedule-patient:{appointment_id}:{slot_id}`

## События

При создании, отмене и переносе записи публикуются события в NATS (см. [События NATS](../api/events.md)).

## Демо-данные

При старте выполняется `seed_demo_data()`:

- врачи (терапевт, хирург);
- услуги с ценами;
- слоты на ближайшие дни;
- профиль демо-клиники.

## RBAC

Врачебные и staff-эндпоинты проверяют заголовок `X-Role` и списки Telegram ID из конфигурации.
