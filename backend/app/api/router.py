from fastapi import APIRouter

from app.modules.system.router import router as system_router

api_router = APIRouter(prefix='/api')
api_router.include_router(system_router)
