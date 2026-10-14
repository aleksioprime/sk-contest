from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, Db
from app.core.storage import StorageError, storage
from app.modules.files import access
from app.modules.files.models import StoredFile
from app.modules.files.service import FileError, save_upload

router = APIRouter(prefix='/v1/files', tags=['files'])
public_router = APIRouter(prefix='/v1/public/files', tags=['public'])


def file_out(stored: StoredFile) -> dict:
    return {
        'id': stored.id,
        'name': stored.original_name,
        'content_type': stored.content_type,
        'size': stored.size,
        'url': f'/api/v1/public/files/{stored.id}' if stored.is_public else f'/api/v1/files/{stored.id}',
    }


@router.post('', status_code=status.HTTP_201_CREATED, summary='Загрузить файл')
async def upload(
    db: Db,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    purpose: Annotated[str, Form(pattern='^(document|image|site_document)$')] = 'document',
) -> dict:
    try:
        stored = await save_upload(db, file, user.id, purpose, is_public=purpose in {'image', 'site_document'})
    except FileError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()
    return file_out(stored)


def _stream(stored: StoredFile, inline: bool) -> StreamingResponse:
    try:
        handle = storage.open(stored.key)
    except StorageError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Файл не найден') from exc
    disposition = 'inline' if inline else 'attachment'
    return StreamingResponse(
        handle,
        media_type=stored.content_type,
        headers={
            'Content-Disposition': f"{disposition}; filename*=UTF-8''{quote(stored.original_name)}",
            'X-Content-Type-Options': 'nosniff',
        },
    )


@router.get('/{file_id}', summary='Скачать файл')
async def download(file_id: int, db: Db, user: CurrentUser) -> StreamingResponse:
    stored = await db.get(StoredFile, file_id)
    if stored is None or not await access.can_read(db, user, stored):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Файл не найден')
    return _stream(stored, inline=stored.content_type in {'application/pdf', 'image/jpeg', 'image/png', 'image/webp'})


@public_router.get('/{file_id}', summary='Публичный файл (обложки, картинки лендингов)')
async def public_download(file_id: int, db: Db) -> StreamingResponse:
    stored = await db.get(StoredFile, file_id)
    if stored is None or not stored.is_public:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Файл не найден')
    response = _stream(stored, inline=True)
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response
