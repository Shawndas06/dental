import logging

import httpx

from shared.config import get_settings

logger = logging.getLogger(__name__)


def telegram_proxy_url() -> str | None:
    value = get_settings().telegram_proxy_url.strip()
    return value or None


def _client_kwargs(**kwargs) -> dict:
    proxy = telegram_proxy_url()
    if proxy:
        kwargs["proxy"] = proxy
    return kwargs


def httpx_async_client(**kwargs) -> httpx.AsyncClient:
    return httpx.AsyncClient(**_client_kwargs(**kwargs))


def httpx_sync_client(**kwargs) -> httpx.Client:
    return httpx.Client(**_client_kwargs(**kwargs))


async def post_telegram_api(url: str, *, json: dict, timeout: float = 10) -> httpx.Response:
    proxy = telegram_proxy_url()
    if proxy:
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as client:
                response = await client.post(url, json=json)
                response.raise_for_status()
                return response
        except Exception as exc:
            logger.warning("Telegram API via proxy failed, retrying direct: %s", exc)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=json)
        response.raise_for_status()
        return response


async def get_telegram_api(url: str, *, params: dict | None = None, timeout: float = 60) -> httpx.Response:
    proxy = telegram_proxy_url()
    if proxy:
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response
        except Exception as exc:
            logger.warning("Telegram API via proxy failed, retrying direct: %s", exc)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response


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
