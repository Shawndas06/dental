import asyncio
import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from nats.aio.client import Client as NATS

from shared.config import get_settings
from shared.events import event_for
from shared.nats import EventPublisher, decode_event
from shared.notification_text import patient_appointment_text, staff_appointment_text
from shared.service_auth import internal_service_headers
from shared.telegram_client import httpx_async_client, post_telegram_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()
publisher = EventPublisher(settings.nats_url)


async def main() -> None:
    await publisher.connect()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scan_reminders, "interval", minutes=15, next_run_time=None)
    scheduler.start()

    nc = NATS()
    await nc.connect(settings.nats_url)
    js = nc.jetstream()
    await js.subscribe("appointments.*", cb=handle_appointment_event, durable="worker_appointments")
    await js.subscribe("appointments.reschedule.*", cb=handle_appointment_event, durable="worker_reschedules")
    await js.subscribe("crm.appointment.sync_requested", cb=handle_crm_sync, durable="worker_crm")
    await js.subscribe("notifications.patient.reminder_24h", cb=handle_notification, durable="worker_reminders")
    logger.info("Worker is running")
    while True:
        await asyncio.sleep(3600)


async def scan_reminders() -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{settings.core_api_url}/api/reminders/due",
            headers=internal_service_headers(),
        )
        response.raise_for_status()
    for appointment in response.json():
        await publisher.publish(
            "notifications.patient.reminder_24h",
            event_for(
                "notifications.patient.reminder_24h",
                f"reminder-24h:{appointment['appointment_id']}",
                appointment,
            ),
        )


async def handle_appointment_event(msg) -> None:
    event = decode_event(msg.data)
    payload = event.payload
    text = staff_appointment_text(event.event_type, payload)
    await _store_notification(settings.staff_group_chat_id or "staff_group", text, payload)
    if settings.staff_group_chat_id:
        await _send_telegram(settings.staff_group_chat_id, text)
    patient_text = patient_appointment_text(event.event_type, payload)
    chat_id = payload.get("chat_id")
    if chat_id and patient_text:
        await _send_telegram(chat_id, patient_text)
    await msg.ack()


async def handle_notification(msg) -> None:
    event = decode_event(msg.data)
    payload = event.payload
    text = f"Напоминание: прием {payload.get('date')} в {payload.get('time', '')[:5]}."
    await _store_notification(payload.get("patient_id", "patient"), text, payload)
    chat_id = payload.get("chat_id")
    if chat_id:
        await _send_telegram(chat_id, text)
    await msg.ack()


async def handle_crm_sync(msg) -> None:
    event = decode_event(msg.data)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                f"{settings.crm_mock_url}/crm/appointments/sync",
                headers=internal_service_headers(),
                json=event.payload,
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning("CRM sync failed: %s", exc)
        await publisher.publish(
            "crm.appointment.sync_failed",
            event_for(
                "crm.appointment.sync_failed",
                f"crm-sync-failed:{event.payload.get('appointment_id')}",
                {"errorCode": "CRM_SYNC_FAILED", "retryable": True, "appointment": event.payload},
            ),
        )
    finally:
        await msg.ack()


async def _store_notification(chat_id: str, text: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{settings.core_api_url}/api/notifications",
            headers=internal_service_headers(),
            json={"chat_id": chat_id, "text": text, "payload": payload},
        )


async def _send_telegram(chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        return
    url = f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/sendMessage"
    try:
        await post_telegram_api(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as exc:
        logger.warning("Telegram sendMessage failed for chat_id=%s: %s", chat_id, exc)


if __name__ == "__main__":
    asyncio.run(main())
