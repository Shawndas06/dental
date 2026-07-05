#!/usr/bin/env python3
"""Wait for a Telegram user and send a one-time notification."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import get_settings
from shared.notification_delivery import DEFAULT_NOTIFY_TEXT, send_target_notification
from shared.telegram_client import get_telegram_api


def _extract_users(payload: dict) -> list[tuple[str, str | None]]:
    users: list[tuple[str, str | None]] = []
    for update in payload.get("result", []):
        for key in ("message", "callback_query", "edited_message"):
            item = update.get(key)
            if not item:
                continue
            from_user = item.get("from") or {}
            chat = item.get("chat") or item.get("message", {}).get("chat") or {}
            user_id = from_user.get("id") or chat.get("id")
            chat_id = chat.get("id") or user_id
            if chat_id:
                users.append((str(chat_id), from_user.get("username")))
    return users


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default=None)
    parser.add_argument("--text", default=DEFAULT_NOTIFY_TEXT)
    parser.add_argument("--hours", type=float, default=8.0)
    args = parser.parse_args()

    settings = get_settings()
    username = (args.username or settings.notify_telegram_username or "").strip()
    if not username or not settings.telegram_bot_token:
        print("NOTIFY_TELEGRAM_USERNAME or TELEGRAM_BOT_TOKEN missing", file=sys.stderr)
        return 1

    token = settings.telegram_bot_token
    base = settings.telegram_api_base.rstrip("/")
    updates_url = f"{base}/bot{token}/getUpdates"
    deadline = asyncio.get_event_loop().time() + args.hours * 3600
    offset = 0
    target = username.lstrip("@").lower()
    print(f"Waiting for @{target} up to {args.hours}h...")

    while asyncio.get_event_loop().time() < deadline:
        response = await get_telegram_api(
            updates_url,
            params={"offset": offset, "timeout": 25, "limit": 20},
            timeout=35,
        )
        payload = response.json()
        for update in payload.get("result", []):
            offset = update["update_id"] + 1
            for chat_id, found_username in _extract_users({"result": [update]}):
                if found_username and found_username.lower() == target:
                    sent = await send_target_notification(chat_id, found_username, args.text)
                    if sent:
                        print(f"Sent notification to @{target} chat_id={chat_id}")
                        return 0
        await asyncio.sleep(0.5)

    print(f"Timeout waiting for @{target}")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
