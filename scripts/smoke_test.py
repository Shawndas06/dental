#!/usr/bin/env python3
"""Smoke checks for the local Docker stack."""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
import time

import httpx

TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
ADMIN = os.environ.get("ADMIN_TOKEN", "")
BASE = os.environ.get("CORE_API_URL", "http://127.0.0.1:8100").replace("core-api:8000", "127.0.0.1:8100")
AI = os.environ.get("AI_ORCHESTRATOR_URL", "http://127.0.0.1:8101").replace("ai-orchestrator:8001", "127.0.0.1:8101")
BOT = os.environ.get("BOT_GATEWAY_URL", "http://127.0.0.1:8180")
CRM = os.environ.get("CRM_MOCK_URL", "http://127.0.0.1:8102").replace("crm-mock:8002", "127.0.0.1:8102")


def proof(telegram_user_id: str) -> str:
    ts = int(time.time())
    digest = hmac.new(TOKEN.encode(), f"{telegram_user_id}:{ts}".encode(), hashlib.sha256).hexdigest()
    return f"{ts}:{digest}"


def svc(telegram_user_id: str | None = None, **extra: str) -> dict[str, str]:
    headers = {"X-Service-Token": TOKEN}
    if telegram_user_id:
        headers["X-Telegram-User-Id"] = telegram_user_id
        headers["X-Patient-Proof"] = proof(telegram_user_id)
    headers.update(extra)
    return headers


def check(name: str, fn) -> bool:
    try:
        response = fn()
        ok = 200 <= response.status_code < 300 or response.status_code in {401, 403, 404}
        print(f"{'OK' if ok else 'FAIL':4}  {name:32}  {response.status_code}")
        return ok
    except Exception as exc:
        print(f"FAIL  {name:32}  {exc}")
        return False


def main() -> int:
    if not TOKEN:
        print("INTERNAL_SERVICE_TOKEN is required", file=sys.stderr)
        return 1

    results = [
        check("core_health", lambda: httpx.get(f"{BASE}/health", timeout=5)),
        check("services_need_token", lambda: httpx.get(f"{BASE}/api/services", timeout=5)),
        check("services_with_token", lambda: httpx.get(f"{BASE}/api/services", headers=svc(), timeout=5)),
        check("crm_need_token", lambda: httpx.post(f"{CRM}/crm/patients/lookup", json={"telegram_user_id": "x"}, timeout=5)),
        check("create_need_proof", lambda: httpx.post(
            f"{BASE}/api/appointments",
            headers={"X-Service-Token": TOKEN, "X-Telegram-User-Id": "attacker"},
            json={
                "patient_id": "pat_demo",
                "doctor_id": "doc_therapist",
                "service_id": "svc_primary",
                "slot_id": "slot_doc_therapist_1_0",
                "visit_type": "primary_consultation",
            },
            timeout=5,
        )),
        check("ai_clinical_refusal", lambda: httpx.post(
            f"{AI}/api/ai/intake",
            headers=svc("smoke_user"),
            json={"telegram_user_id": "smoke_user", "text": "какие антибиотики пить при флюсе?"},
            timeout=5,
        )),
        check("bot_health", lambda: httpx.get(f"{BOT}/health", timeout=5)),
    ]
    if ADMIN:
        results.append(check("admin_dashboard", lambda: httpx.get(
            f"{BASE}/api/admin/dashboard",
            headers={"X-Admin-Token": ADMIN},
            timeout=5,
        )))
        results.append(check("demo_run", lambda: httpx.post(
            f"{BASE}/api/admin/demo/run",
            headers={"X-Admin-Token": ADMIN},
            timeout=60,
        )))

    ai_response = httpx.post(
        f"{AI}/api/ai/intake",
        headers=svc("smoke_user"),
        json={"telegram_user_id": "smoke_user", "text": "какие антибиотики пить при флюсе?"},
        timeout=5,
    )
    if ai_response.status_code == 200:
        intent = ai_response.json().get("intent")
        clinical_ok = intent == "clinical_question"
        print(f"{'OK' if clinical_ok else 'FAIL':4}  ai_intent_clinical               {intent}")
        results.append(clinical_ok)

    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
