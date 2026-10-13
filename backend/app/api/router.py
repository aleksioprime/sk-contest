from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.people.router import router as people_router
from app.modules.system.router import router as system_router

api_router = APIRouter(prefix='/api')
api_router.include_router(system_router)
api_router.include_router(auth_router)
api_router.include_router(people_router)
