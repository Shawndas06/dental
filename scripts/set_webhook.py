import asyncio

import httpx

from shared.config import get_settings
from shared.telegram_client import httpx_async_client


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is empty")
    if not settings.telegram_webhook_url:
        raise SystemExit("TELEGRAM_WEBHOOK_URL is empty")

    url = f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/setWebhook"
    payload = {
        "url": settings.telegram_webhook_url,
        "drop_pending_updates": True,
    }
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret

    async with httpx_async_client(timeout=10) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        print(response.json())


if __name__ == "__main__":
    asyncio.run(main())
