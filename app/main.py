# -*- coding: utf-8 -*-
"""FastAPI app — production: đăng nhập + phân quyền + PostgreSQL."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import APP_NAME, SECRET_KEY, SESSION_HOURS
from .cli import init_db
from .routers import admin, auth_routes, entry, pages, reports, summary

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME, docs_url="/api/docs", redoc_url=None)

    app.add_middleware(
        SessionMiddleware,
        secret_key=SECRET_KEY,
        max_age=SESSION_HOURS * 3600,
        same_site="lax",
        https_only=False,  # đặt True khi đã có HTTPS (nginx) — env APP_HTTPS=1
    )

    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

    def _vn_date(d) -> str:
        return f"{d.day}/{d.month}/{d.year}"

    def _vn_full(d) -> str:
        return f"Ngày {d.day} tháng {d.month} năm {d.year}"

    templates.env.filters["vnd"] = _vn_date
    templates.env.filters["vnfull"] = _vn_full
    app.state.templates = templates

    app.include_router(auth_routes.router)
    app.include_router(pages.router)
    app.include_router(entry.router)
    app.include_router(reports.router)
    app.include_router(admin.router)
    app.include_router(summary.router)

    @app.exception_handler(403)
    async def _forbidden(request: Request, exc):
        return templates.TemplateResponse(
            request,
            "403.html",
            {"user": None, "detail": getattr(exc, "detail", "Không có quyền truy cập.")},
            status_code=403,
        )

    @app.on_event("startup")
    def _startup():
        init_db(with_seed=True)

    return app


app = create_app()
