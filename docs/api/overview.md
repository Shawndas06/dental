# API — обзор

Базовые URL в Docker Compose (на хосте):

| Сервис | Base URL |
|--------|----------|
| bot-gateway | `http://127.0.0.1:8180` |
| core-api | `http://127.0.0.1:8100` |
| ai-orchestrator | `http://127.0.0.1:8101` |
| crm-mock | `http://127.0.0.1:8102` |
| admin | `http://127.0.0.1:8190` |

## Заголовки аутентификации

### Core API (`/api/*`)

```http
X-Service-Token: <INTERNAL_SERVICE_TOKEN>
```

Для операций от имени пациента (запись, отмена, перенос):

```http
X-Telegram-User-Id: <telegram user id>
X-Patient-Proof: <unix_ts>:<hmac-sha256>
```

Врачебные эндпоинты:

```http
X-Role: doctor
X-Telegram-User-Id: <id из doctor.telegram_user_id>
```

### Admin API (`/api/admin/*`)

```http
X-Admin-Token: <ADMIN_TOKEN>
```

### Idempotency

```http
Idempotency-Key: <уникальный ключ>
```

## Bot Gateway

| Метод | Путь | Auth |
|-------|------|------|
| GET | `/health` | — |
| POST | `/api/telegram/webhook` | `X-Telegram-Bot-Api-Secret-Token` |
| POST | `/debug/simulate` | `X-Debug-Token` (если `DEBUG_API_ENABLED=true`) |
| GET | `/debug/ai-call-count` | `X-Debug-Token` |

## Core API — пользователи и пациенты

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/users/telegram/register` | Upsert Telegram-пользователя |
| POST | `/api/patients/lookup` | Lookup / create patient |
| GET | `/api/patients/by-telegram/{telegram_user_id}` | Пациент по Telegram ID |
| POST | `/api/patients/quick-register` | Быстрая регистрация |

## Core API — справочники

| Метод | Путь | Параметры |
|-------|------|-----------|
| GET | `/api/doctors` | — |
| GET | `/api/services` | `doctor_id`, `category` |
| GET | `/api/pricing/doctor/{doctor_id}` | — |
| GET | `/api/clinic-profile` | — |
| GET | `/api/clinic-profile/service/{service_name}/available` | — |

## Core API — расписание

| Метод | Путь | Параметры |
|-------|------|-----------|
| GET | `/api/schedule/slots/available` | `service_id`, `doctor_id`, `limit` |
| GET | `/api/calendar/doctor/{doctor_id}` | `X-Role: doctor` + проверка ID |
| GET | `/api/calendar/patient/{patient_id}` | Patient proof |
| GET | `/api/calendar/summary` | Сводка для админки |

## Core API — записи

| Метод | Путь | Idempotency |
|-------|------|-------------|
| POST | `/api/appointments` | Да |
| GET | `/api/appointments/patient/{patient_id}` | — |
| GET | `/api/appointments/doctor/{doctor_id}` | — |
| POST | `/api/appointments/{id}/cancel` | Да |
| POST | `/api/appointments/{id}/reschedule/by-patient` | Да |
| POST | `/api/appointments/{id}/reschedule/request-by-doctor` | Да |
| POST | `/api/reschedule/{approval_id}/approve` | — |
| POST | `/api/reschedule/{approval_id}/reject` | — |

### Создание записи

```http
POST /api/appointments
X-Service-Token: <token>
X-Telegram-User-Id: 1001
X-Patient-Proof: 1710000000:abc...
Idempotency-Key: appointment-create:1001:slot_doc_therapist_1_0
Content-Type: application/json

{
  "patient_id": "pat_...",
  "doctor_id": "doc_therapist",
  "service_id": "svc_primary",
  "slot_id": "slot_doc_therapist_1_0",
  "visit_type": "primary_consultation"
}
```

Ответы:

- `201` — запись создана
- `403` — нет patient proof / чужой patient_id
- `409` — слот уже занят

## Core API — внутренние

| Метод | Путь | Auth |
|-------|------|------|
| GET | `/api/reminders/due` | `X-Service-Token` |
| POST | `/api/notifications` | `X-Service-Token` |
| GET | `/debug/events` | `X-Debug-Token` |

!!! warning "Аудит"
    Публичный `GET /api/audit` **удалён**. Журнал: `GET /api/admin/audit` с `X-Admin-Token`.

## Admin API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/admin/dashboard` | Статистика |
| GET | `/api/admin/appointments` | Список записей |
| GET | `/api/admin/audit` | Журнал аудита |
| POST | `/api/admin/demo/run` | Автодемо |

## AI Orchestrator

| Метод | Путь | Auth |
|-------|------|------|
| POST | `/api/ai/intake` | `X-Service-Token` |

Body: `{ "telegram_user_id", "text" }`

## CRM Mock

Все пути требуют `X-Service-Token`.

| Метод | Путь |
|-------|------|
| POST | `/crm/patients/lookup` |
| GET | `/crm/doctors` |
| GET | `/crm/services` |
| POST | `/crm/appointments/sync` |

## Схемы данных

Основные Pydantic-модели в `shared/schemas.py`:

- `UserCreate`, `PatientRead`, `AppointmentRead`
- `ServiceRead`, `SlotRead`, `DoctorRead`
- `Screen`, `Button`, `IntakeResponse`
