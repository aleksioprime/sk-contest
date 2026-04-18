from fastapi import APIRouter

from src.schemas import AnonymousNamePayload, CommentPayload, LevelPayload
from src.services.anonymous_evaluation_service import anonymous_evaluation_service

router = APIRouter()


@router.get('/{token}')
async def get_evaluation_bundle(token: str):
    return await anonymous_evaluation_service.get_bundle(token)


@router.patch('/{token}/criteria/{criterion_id}/level')
async def set_level(token: str, criterion_id: int, payload: LevelPayload):
    return await anonymous_evaluation_service.set_level(token, criterion_id, payload.level_id)


@router.patch('/{token}/criteria/{criterion_id}/comment')
async def set_item_comment(token: str, criterion_id: int, payload: CommentPayload):
    return await anonymous_evaluation_service.set_item_comment(token, criterion_id, payload.comment)


@router.patch('/{token}/comment')
async def set_evaluation_comment(token: str, payload: CommentPayload):
    return await anonymous_evaluation_service.set_evaluation_comment(token, payload.comment)


@router.patch('/{token}/anonymous-name')
async def set_anonymous_name(token: str, payload: AnonymousNamePayload):
    return await anonymous_evaluation_service.set_anonymous_name(token, payload.anonymous_name)
