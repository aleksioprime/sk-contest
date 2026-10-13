from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.csrf import OriginCheckMiddleware
from app.core.logging import RequestLoggingMiddleware, setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        docs_url='/api/docs',
        openapi_url='/api/openapi.json',
        default_response_class=ORJSONResponse,
    )
    app.add_middleware(OriginCheckMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(api_router)
    return app


app = create_app()
