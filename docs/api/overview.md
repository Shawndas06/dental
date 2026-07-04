# API — обзор

Базовые URL в Docker Compose (на хосте):

| Сервис | Base URL |
|--------|----------|
| bot-gateway | `http://127.0.0.1:8180` |
| core-api | `http://127.0.0.1:8100` |
| ai-orchestrator | `http://127.0.0.1:8101` |
| crm-mock | `http://127.0.0.1:8102` |

## Bot Gateway

| Метод | Путь | Auth |
|-------|------|------|
| GET | `/health` | — |
| POST | `/api/telegram/webhook` | `X-Telegram-Bot-Api-Secret-Token` |
| POST | `/debug/simulate` | — (только dev) |

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
| GET | `/api/calendar/doctor/{doctor_id}` | Header `X-Role: doctor` |
| GET | `/api/calendar/patient/{patient_id}` | — |

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
- `409` — слот уже занят

## Core API — прочее

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/reminders/due` | Записи для напоминания |
| POST | `/api/notifications` | Создать уведомление |
| GET | `/api/audit` | Журнал аудита |
| GET | `/debug/events` | Опубликованные события (dev) |

## AI Orchestrator

| Метод | Путь | Body |
|-------|------|------|
| POST | `/api/ai/intake` | `{ "telegram_user_id", "text" }` |

## CRM Mock

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
