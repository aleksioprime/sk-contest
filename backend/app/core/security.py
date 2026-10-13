import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings

ALGORITHM = 'HS256'


class TokenError(Exception):
    pass


def now_utc() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: int, session_id: int) -> str:
    issued = now_utc()
    payload = {
        'sub': str(user_id),
        'sid': str(session_id),
        'type': 'access',
        'iat': issued,
        'exp': issued + timedelta(minutes=settings.auth.access_ttl_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError('Недействительный токен') from exc
    if payload.get('type') != 'access':
        raise TokenError('Неверный тип токена')
    return payload


def new_secret() -> str:
    """Случайный токен для ссылок и сессий. В БД хранится только его хеш."""
    return secrets.token_urlsafe(32)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sign_state(data: dict, ttl_minutes: int = 10) -> str:
    """Подписанное короткоживущее значение (state OAuth и code_verifier в cookie)."""
    payload = {**data, 'type': 'state', 'exp': now_utc() + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def read_state(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError('Сессия входа устарела') from exc
    if payload.get('type') != 'state':
        raise TokenError('Неверный тип токена')
    return payload
