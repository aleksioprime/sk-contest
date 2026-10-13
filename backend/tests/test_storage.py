import io

import pytest

from app.core.storage import LocalStorage, StorageError


def test_save_open_delete(tmp_path):
    storage = LocalStorage(tmp_path)
    key = storage.save(io.BytesIO(b'content'), suffix='work.PDF')
    assert key.endswith('.pdf')
    with storage.open(key) as file:
        assert file.read() == b'content'
    assert storage.size(key) == 7
    storage.delete(key)
    with pytest.raises(StorageError):
        storage.open(key)


def test_rejects_path_outside_root(tmp_path):
    storage = LocalStorage(tmp_path / 'files')
    with pytest.raises(StorageError):
        storage.open('../../etc/passwd')
