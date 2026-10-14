from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import storage
from app.modules.files.models import StoredFile

MAX_SIZE = 25 * 1024 * 1024
IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
DOCUMENT_TYPES = IMAGE_TYPES | {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/zip',
    'text/plain',
}
PURPOSES = {'document': DOCUMENT_TYPES, 'image': IMAGE_TYPES}


class FileError(Exception):
    pass


class _LimitedReader:
    """Читает поток и прерывает загрузку, если файл больше лимита."""

    def __init__(self, stream, limit: int):
        self.stream, self.limit, self.size = stream, limit, 0

    def read(self, n: int = -1) -> bytes:
        chunk = self.stream.read(n)
        self.size += len(chunk)
        if self.size > self.limit:
            raise FileError(f'Файл больше {self.limit // (1024 * 1024)} МБ')
        return chunk


async def save_upload(
    session: AsyncSession, upload: UploadFile, owner_id: int, purpose: str = 'document', is_public: bool = False
) -> StoredFile:
    content_type = (upload.content_type or '').split(';')[0].strip().lower()
    if content_type not in PURPOSES[purpose]:
        raise FileError('Этот тип файла не поддерживается')
    name = Path(upload.filename or 'file').name[:255]
    reader = _LimitedReader(upload.file, MAX_SIZE)
    key = storage.save(reader, suffix=name)
    if reader.size == 0:
        storage.delete(key)
        raise FileError('Файл пустой')
    stored = StoredFile(
        key=key, original_name=name, content_type=content_type, size=reader.size, owner_id=owner_id, is_public=is_public
    )
    session.add(stored)
    await session.flush()
    return stored
