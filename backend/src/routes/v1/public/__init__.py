from fastapi import APIRouter

from src.routes.v1.public.evaluations import router as evaluations_router

router = APIRouter()
router.include_router(evaluations_router, prefix='/evaluations')
