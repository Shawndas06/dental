import json
import secrets
import time
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from shared.config import get_settings
from shared.security import safe_compare_digest
from shared.startup_checks import warn_insecure_defaults

settings = get_settings()
app = FastAPI(title="Dental Bot Admin", version="0.1.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

CORE_API = settings.core_api_url.rstrip("/")
if "core-api:" in CORE_API:
    CORE_API = "http://127.0.0.1:8100"
SESSION_COOKIE = "admin_session"
CSRF_COOKIE = "admin_csrf"
SESSION_TTL_SECONDS = 86400
LOGIN_SESSIONS: dict[str, float] = {}


def _prune_sessions() -> None:
    now = time.monotonic()
    expired = [session_id for session_id, expires_at in LOGIN_SESSIONS.items() if expires_at <= now]
    for session_id in expired:
        LOGIN_SESSIONS.pop(session_id, None)


def _is_authenticated(request: Request) -> bool:
    _prune_sessions()
    session_id = request.cookies.get(SESSION_COOKIE, "")
    expires_at = LOGIN_SESSIONS.get(session_id or "")
    return bool(session_id and expires_at and expires_at > time.monotonic())


def _csrf_token(request: Request) -> str:
    token = request.cookies.get(CSRF_COOKIE)
    if token:
        return token
    return secrets.token_urlsafe(32)


def _verify_csrf(request: Request, form_token: str | None) -> bool:
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    return bool(form_token and cookie_token and safe_compare_digest(form_token, cookie_token))


def _headers(request: Request) -> dict[str, str]:
    if _is_authenticated(request):
        return {"X-Admin-Token": settings.admin_token}
    return {}


def _set_session_cookies(response: Response, csrf_token: str) -> None:
    session_id = secrets.token_urlsafe(32)
    LOGIN_SESSIONS[session_id] = time.monotonic() + SESSION_TTL_SECONDS
    response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="strict", max_age=SESSION_TTL_SECONDS)
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=True, samesite="strict", max_age=SESSION_TTL_SECONDS)


async def _api(request: Request, method: str, path: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(timeout=20) as client:
        return await client.request(method, f"{CORE_API}{path}", headers=_headers(request), **kwargs)


def _template_context(request: Request, **extra: Any) -> dict[str, Any]:
    return {"csrf_token": _csrf_token(request), **extra}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    csrf_token = _csrf_token(request)
    response = templates.TemplateResponse(
        request,
        "login.html",
        _template_context(request, error=None, title="Вход"),
    )
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=True, samesite="strict")
    return response


@app.post("/login")
async def login_submit(
    request: Request,
    token: str = Form(...),
    csrf_token: str = Form(...),
) -> Response:
    if not _verify_csrf(request, csrf_token):
        return RedirectResponse("/login?error=1", status_code=302)
    if not settings.admin_token or not safe_compare_digest(token, settings.admin_token):
        return RedirectResponse("/login?error=1", status_code=302)
    response = RedirectResponse("/dashboard", status_code=302)
    _set_session_cookies(response, secrets.token_urlsafe(32))
    return response


@app.get("/logout")
async def logout(request: Request) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        LOGIN_SESSIONS.pop(session_id, None)
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    response = await _api(request, "GET", "/api/admin/dashboard")
    stats = response.json() if response.status_code == 200 else {}
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _template_context(request, title="Дашборд", stats=stats, apiError=response.status_code != 200),
    )


@app.get("/patients", response_class=HTMLResponse)
async def patients_page(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    response = await _api(request, "GET", "/api/admin/patients")
    items = response.json() if response.status_code == 200 else []
    return templates.TemplateResponse(
        request,
        "table.html",
        _template_context(
            request,
            title="Пациенты",
            items=items,
            columns=["name", "telegramUserId", "phone", "isPrimary", "createdAt"],
            labels=["Имя", "Telegram ID", "Телефон", "Первичный", "Создан"],
        ),
    )


@app.get("/appointments", response_class=HTMLResponse)
async def appointments_page(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    response = await _api(request, "GET", "/api/admin/appointments")
    items = response.json() if response.status_code == 200 else []
    return templates.TemplateResponse(
        request,
        "table.html",
        _template_context(
            request,
            title="Записи",
            items=items,
            columns=["date", "time", "patientName", "doctorName", "serviceName", "status"],
            labels=["Дата", "Время", "Пациент", "Врач", "Услуга", "Статус"],
        ),
    )


@app.get("/doctors", response_class=HTMLResponse)
async def doctors_page(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    doctors = (await _api(request, "GET", "/api/admin/doctors")).json()
    services = (await _api(request, "GET", "/api/admin/services")).json()
    return templates.TemplateResponse(
        request,
        "doctors.html",
        _template_context(request, title="Врачи и услуги", doctors=doctors, services=services),
    )


@app.get("/slots", response_class=HTMLResponse)
async def slots_page(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    response = await _api(request, "GET", "/api/admin/slots", params={"limit": 80})
    items = response.json() if response.status_code == 200 else []
    return templates.TemplateResponse(
        request,
        "table.html",
        _template_context(
            request,
            title="Слоты",
            items=items,
            columns=["date", "time", "doctorId", "slotId", "status"],
            labels=["Дата", "Время", "Врач", "Slot ID", "Статус"],
        ),
    )


@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    response = await _api(request, "GET", "/api/admin/audit")
    items = response.json() if response.status_code == 200 else []
    return templates.TemplateResponse(
        request,
        "audit.html",
        _template_context(request, title="Аудит", items=items),
    )


@app.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "demo.html",
        _template_context(request, title="Демо-сценарий", result=None),
    )


@app.post("/demo/reset")
async def demo_reset(request: Request, csrf_token: str = Form(...)) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    if not _verify_csrf(request, csrf_token):
        return RedirectResponse("/demo?error=csrf", status_code=302)
    await _api(request, "POST", "/api/admin/demo/reset")
    return RedirectResponse("/demo?reset=1", status_code=302)


@app.post("/demo/run")
async def demo_run(request: Request, csrf_token: str = Form(...)) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    if not _verify_csrf(request, csrf_token):
        return RedirectResponse("/demo?error=csrf", status_code=302)
    response = await _api(request, "POST", "/api/admin/demo/run")
    result = response.json() if response.status_code == 200 else {"success": False, "error": response.text}
    return templates.TemplateResponse(
        request,
        "demo.html",
        _template_context(
            request,
            title="Демо-сценарий",
            result=result,
            result_json=json.dumps(result, ensure_ascii=False, indent=2),
        ),
    )


if __name__ == "__main__":
    warn_insecure_defaults()
    uvicorn.run("services.admin.main:app", host="127.0.0.1", port=settings.admin_port)
