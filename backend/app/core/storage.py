"""Хранение загруженных файлов на диске.

Файл лежит по ключу вида `ab/cd/<uuid>.<ext>`. В БД хранится только ключ и метаданные.
Модули работают с файлами только через этот класс, чтобы хранилище можно было заменить.
"""

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings


class StorageError(Exception):
    pass


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def save(self, stream: BinaryIO, suffix: str = '') -> str:
        name = uuid.uuid4().hex
        ext = Path(suffix).suffix.lower()[:10] if suffix else ''
        key = f'{name[:2]}/{name[2:4]}/{name}{ext}'
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('wb') as target:
            shutil.copyfileobj(stream, target)
        return key

    def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        if not path.is_file():
            raise StorageError(f'Файл не найден: {key}')
        return path.open('rb')

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def size(self, key: str) -> int:
        return self._path(key).stat().st_size

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise StorageError('Недопустимый ключ файла')
        return path


storage = LocalStorage(settings.storage_dir)
