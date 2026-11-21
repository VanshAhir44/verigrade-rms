from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.faculty import router as faculty_router
from app.routers.student import router as student_router
from app.routers.verify import router as verify_router
from app.routers.ws import router as ws_router


def create_app() -> FastAPI:
    is_prod = settings.ENVIRONMENT.lower() == "production"
    application = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        if request.url.path.startswith(f"{settings.API_V1_PREFIX}/auth") or request.url.path.startswith(
            f"{settings.API_V1_PREFIX}/student"
        ):
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.get(f"{settings.API_V1_PREFIX}/health", tags=["Health"])
    async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}

    application.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    application.include_router(admin_router, prefix=settings.API_V1_PREFIX)
    application.include_router(faculty_router, prefix=settings.API_V1_PREFIX)
    application.include_router(student_router, prefix=settings.API_V1_PREFIX)
    application.include_router(verify_router, prefix=settings.API_V1_PREFIX)
    application.include_router(ws_router)
    return application


app = create_app()
