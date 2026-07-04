#!/usr/bin/env python3
"""CLI: запуск автоматического демо-сценария."""

import argparse
import asyncio
import json
import sys

from services.core_api.demo_scenario import run_demo_scenario
from shared.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dental bot demo scenario")
    parser.add_argument("--core-api", default=None)
    parser.add_argument("--bot-gateway", default=None)
    parser.add_argument("--ai-orchestrator", default=None)
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    core = args.core_api or _host_url(settings.core_api_url, 8100)
    bot = args.bot_gateway or settings.bot_gateway_url
    ai = args.ai_orchestrator or _host_url(settings.ai_orchestrator_url, 8101)

    result = asyncio.run(
        run_demo_scenario(
            core,
            bot,
            ai,
            admin_token=settings.admin_token,
            skip_reset=args.no_reset,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


def _host_url(url: str, default_port: int) -> str:
    if "core-api:" in url or "ai-orchestrator:" in url:
        return f"http://127.0.0.1:{default_port}"
    return url.rstrip("/")


if __name__ == "__main__":
    sys.exit(main())
