from fastapi import APIRouter

from src.routes.v1.public import router as public_router

router = APIRouter()
router.include_router(public_router, prefix='/public', tags=['public'])
