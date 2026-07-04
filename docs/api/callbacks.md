# Callback-кнопки

Telegram inline-кнопки используют поле `callback_data` в формате:

```
namespace:action[:arg1[:arg2...]]
```

Максимальная длина: **64 символа** (ограничение Telegram).

## Разрешённые namespace

| Namespace | Примеры |
|-----------|---------|
| `menu` | `menu:main`, `menu:contacts` |
| `nav` | `nav:back` |
| `register` | `register:confirm` |
| `appointment` | `appointment:start`, `appointment:list`, `appointment:cancel:{id}` |
| `service` | `service:select:{service_id}` |
| `slot` | `slot:select:{slot_id}` |
| `reschedule` | `reschedule:start:{id}`, `reschedule:slot:{appt}:{slot}`, `reschedule:approve:{id}` |
| `pricing` | `pricing:list` |
| `calendar` | `calendar:doctor:today` |

Полный список: `shared/callbacks.py` → `ALLOWED_PREFIXES`.

## Правила безопасности

!!! warning "PII запрещён"
    В `callback_data` **нельзя** передавать:

    - телефон (9+ цифр подряд);
    - email (`@`);
    - символ `+` в номере.

Используются только внутренние ID (`slot_id`, `appointment_id`, `service_id`).

## Idempotency

`CallbackAction.idempotency_key` формируется как `namespace:action:args` и используется при создании записей и переносов.

## Примеры

| Кнопка | callback_data |
|--------|---------------|
| Главное меню | `menu:main` |
| Записаться | `appointment:start` |
| Услуга | `service:select:svc_primary` |
| Слот | `slot:select:slot_doc_therapist_1_0` |
| Отмена записи | `appointment:cancel:appt_abc123` |
| Быстрая регистрация | `register:confirm` |

## Layout кнопок

Экран (`Screen`) поддерживает `button_layout` — массив ширин строк:

```python
Screen(
    text="...",
    buttons=[...],
    button_layout=[2, 2, 1],  # две пары + одна кнопка на всю строку
)
```

Рендеринг: `services/bot_gateway/rendering.py` → `to_telegram_markup`.

## Публичные callback без регистрации

Доступны без быстрой регистрации:

- `pricing:list`
- `menu:contacts`
- `menu:main`, `nav:back`
- `calendar:doctor:today`

Остальные сценарии требуют `POST /api/patients/quick-register`.
