import hmac
import json
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from shared.config import get_settings

settings = get_settings()
app = FastAPI(title="Dental Bot Admin", version="0.1.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

CORE_API = settings.core_api_url.rstrip("/")
if "core-api:" in CORE_API:
    CORE_API = "http://127.0.0.1:8100"
COOKIE_NAME = "admin_session"


def _headers(request: Request) -> dict[str, str]:
    token = request.cookies.get(COOKIE_NAME, "")
    if token and settings.admin_token and hmac.compare_digest(token, settings.admin_token):
        return {"X-Admin-Token": settings.admin_token}
    return {}


def _is_authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME, "")
    return bool(settings.admin_token and token and hmac.compare_digest(token, settings.admin_token))


async def _api(request: Request, method: str, path: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(timeout=20) as client:
        return await client.request(method, f"{CORE_API}{path}", headers=_headers(request), **kwargs)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "title": "Вход"},
    )


@app.post("/login")
async def login_submit(token: str = Form(...)) -> Response:
    if not settings.admin_token or not hmac.compare_digest(token, settings.admin_token):
        return RedirectResponse("/login?error=1", status_code=302)
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(COOKIE_NAME, settings.admin_token, httponly=True, samesite="lax")
    return response


@app.get("/logout")
async def logout() -> Response:
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
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
        {"title": "Дашборд", "stats": stats, "apiError": response.status_code != 200},
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
        {
            "title": "Пациенты",
            "items": items,
            "columns": ["name", "telegramUserId", "phone", "isPrimary", "createdAt"],
            "labels": ["Имя", "Telegram ID", "Телефон", "Первичный", "Создан"],
        },
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
        {
            "title": "Записи",
            "items": items,
            "columns": ["date", "time", "patientName", "doctorName", "serviceName", "status"],
            "labels": ["Дата", "Время", "Пациент", "Врач", "Услуга", "Статус"],
        },
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
        {"title": "Врачи и услуги", "doctors": doctors, "services": services},
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
        {
            "title": "Слоты",
            "items": items,
            "columns": ["date", "time", "doctorId", "slotId", "status"],
            "labels": ["Дата", "Время", "Врач", "Slot ID", "Статус"],
        },
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
        {"title": "Аудит", "items": items},
    )


@app.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "demo.html",
        {"title": "Демо-сценарий", "result": None},
    )


@app.post("/demo/reset")
async def demo_reset(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    await _api(request, "POST", "/api/admin/demo/reset")
    return RedirectResponse("/demo?reset=1", status_code=302)


@app.post("/demo/run")
async def demo_run(request: Request) -> Response:
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    response = await _api(request, "POST", "/api/admin/demo/run")
    result = response.json() if response.status_code == 200 else {"success": False, "error": response.text}
    return templates.TemplateResponse(
        request,
        "demo.html",
        {
            "title": "Демо-сценарий",
            "result": result,
            "result_json": json.dumps(result, ensure_ascii=False, indent=2),
        },
    )


if __name__ == "__main__":
    uvicorn.run("services.admin.main:app", host="0.0.0.0", port=settings.admin_port)
