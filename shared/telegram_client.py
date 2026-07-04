import httpx

from shared.config import get_settings


def telegram_proxy_url() -> str | None:
    value = get_settings().telegram_proxy_url.strip()
    return value or None


def httpx_async_client(**kwargs) -> httpx.AsyncClient:
    proxy = telegram_proxy_url()
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


def create_telegram_bot():
    settings = get_settings()
    if not settings.telegram_bot_token:
        return None
    try:
        from aiogram import Bot
    except ModuleNotFoundError:
        return None

    proxy = telegram_proxy_url()
    if proxy:
        from aiogram.client.session.aiohttp import AiohttpSession

        session = AiohttpSession(proxy=proxy)
        return Bot(settings.telegram_bot_token, session=session)
    return Bot(settings.telegram_bot_token)
