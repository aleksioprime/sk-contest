from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from sk_common.web import add_common_middleware, setup_logging

from app.api.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        docs_url='/api/docs',
        openapi_url='/api/openapi.json',
        default_response_class=ORJSONResponse,
    )
    add_common_middleware(app)
    app.include_router(api_router)
    return app


app = create_app()
