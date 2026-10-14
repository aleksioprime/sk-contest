from fastapi import APIRouter

from app.modules.applications.router import router as applications_router
from app.modules.auth.router import router as auth_router
from app.modules.evaluation.router import public_router as public_evaluation_router
from app.modules.evaluation.router import router as evaluation_router
from app.modules.events.router import public_router as public_events_router
from app.modules.events.router import router as events_router
from app.modules.files.router import public_router as public_files_router
from app.modules.files.router import router as files_router
from app.modules.people.router import router as people_router
from app.modules.system.router import router as system_router

api_router = APIRouter(prefix='/api')
api_router.include_router(system_router)
api_router.include_router(auth_router)
api_router.include_router(people_router)
api_router.include_router(events_router)
api_router.include_router(public_events_router)
api_router.include_router(applications_router)
api_router.include_router(files_router)
api_router.include_router(evaluation_router)
api_router.include_router(public_evaluation_router)
api_router.include_router(public_files_router)
