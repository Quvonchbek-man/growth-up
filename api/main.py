"""FastAPI ilovasi — Mini App uchun API va statik fayllar.

Bir port, bir tunnel: qurilgan React fayllari (`web/dist`) ham shu server
orqali tarqatiladi. Ikkita origin bo'lganda CORS, cookie va ikkita tunnel
muammosi paydo bo'lardi — kichik loyihada bu keraksiz og'irlik.

Ishlab chiqish paytida Vite o'z serverida (5173) turadi va API'ga
`CORS_ORIGINS` orqali murojaat qiladi.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routers import api_router
from shared.config import settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Duo Growth API",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,  # initData sarlavhada keladi, cookie ishlatilmaydi
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router)

    @app.get("/api/health")
    async def health() -> dict:
        return {
            "ok": True,
            "auth": "on" if settings.check_init_data else "OFF (dev)",
            "webapp_url": settings.webapp_url or None,
        }

    _mount_web(app)
    return app


def _mount_web(app: FastAPI) -> None:
    """Qurilgan Mini App'ni tarqatadi. Hali qurilmagan bo'lsa — tushuntirish beradi."""
    dist: Path = settings.web_dist_dir
    index = dist / "index.html"

    if not index.exists():
        logger.warning("web/dist topilmadi — Mini App qurilmagan (npm run build)")

        @app.get("/")
        async def not_built() -> JSONResponse:
            return JSONResponse(
                {
                    "error": "Mini App hali qurilmagan",
                    "nima_qilish": "web/ papkasida `npm install && npm run build`",
                    "api": "/api/docs",
                },
                status_code=503,
            )

        return

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    # index.html hech qachon keshdan olinmasin. Ichidagi havolalar qurilma
    # nomiga bog'langan (`assets/index-A1b2C3.js`) — eski index qolsa, ilova
    # yangi qurilmani umuman so'ramaydi va foydalanuvchi eski versiyada
    # muzlab qoladi. `/assets/*` esa nomi hash'li, keshda qolgani ma'qul.
    no_cache = {"Cache-Control": "no-cache, must-revalidate"}

    @app.get("/")
    async def spa_root() -> FileResponse:
        return FileResponse(index, headers=no_cache)

    # Marshrutlash hash (`/#/today`) orqali ketadi, lekin to'g'ridan-to'g'ri
    # ochilgan yo'llar ham index.html ni qaytarsin
    @app.get("/{path:path}")
    async def spa_fallback(path: str) -> FileResponse:
        candidate = dist / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index, headers=no_cache)


app = create_app()
