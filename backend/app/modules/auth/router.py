import base64
import hashlib
import logging
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import exists, select

from app.core.config import settings
from app.core.deps import CurrentUser, Db
from app.core.queue import Queue, get_queue
from app.core.redis import get_redis
from app.core.security import TokenError, decode_access_token, new_secret, read_state, sign_state
from app.modules.applications.models import Application
from app.modules.auth import service
from app.modules.auth.models import AuthSession
from app.modules.auth.schemas import LoginResult, MagicLinkRequest, MagicLinkVerify, Me, Providers
from app.modules.events.models import EventMember
from app.modules.people.schemas import UserOut
from app.modules.people.service import ensure_user, upsert_person_from_profile
from app.modules.people.skolstream import SkolstreamClient, SkolstreamError, get_skolstream_client

logger = logging.getLogger('sk_events.auth')

router = APIRouter(prefix='/v1/auth', tags=['auth'])

OAUTH_COOKIE = 'ske_oauth'
REFRESH_PATH = '/api/v1/auth'


def _set_session_cookies(response: Response, access: str, refresh: str) -> None:
    common = {'httponly': True, 'secure': settings.cookie_secure, 'samesite': 'lax'}
    response.set_cookie(
        settings.auth.access_cookie, access, max_age=settings.auth.access_ttl_minutes * 60, path='/', **common
    )
    response.set_cookie(
        settings.auth.refresh_cookie,
        refresh,
        max_age=settings.auth.refresh_ttl_days * 86400,
        path=REFRESH_PATH,
        **common,
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.auth.access_cookie, path='/')
    response.delete_cookie(settings.auth.refresh_cookie, path=REFRESH_PATH)


def _client_info(request: Request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get('x-forwarded-for', '')
    ip = forwarded.split(',')[0].strip() or (request.client.host if request.client else None)
    return request.headers.get('user-agent'), ip


def _callback_url() -> str:
    return f'{settings.app_url.rstrip("/")}/api/v1/auth/skolstream/callback'


@router.get('/providers', response_model=Providers, summary='Доступные способы входа')
async def providers() -> Providers:
    return Providers(skolstream=settings.skolstream.enabled)


@router.post('/magic-link', status_code=status.HTTP_202_ACCEPTED, summary='Отправить ссылку для входа на email')
async def request_magic_link(payload: MagicLinkRequest, db: Db, queue: Annotated[Queue, Depends(get_queue)]) -> dict:
    try:
        await service.request_magic_link(db, get_redis(), queue, payload.email, payload.next)
    except service.RateLimited as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    await db.commit()
    return {'detail': 'Письмо со ссылкой для входа отправлено'}


@router.post('/magic-link/verify', response_model=LoginResult, summary='Войти по ссылке из письма')
async def verify_magic_link(payload: MagicLinkVerify, request: Request, response: Response, db: Db) -> LoginResult:
    try:
        user, next_path, purpose = await service.consume_magic_link(db, payload.token)
        method = 'judge_qr' if purpose == 'judge_qr' else 'magic_link'
        access, refresh = await service.open_session(db, user, method, *_client_info(request))
    except service.AuthError as exc:
        await db.commit()  # фиксируем погашение ссылки даже при отказе во входе
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()
    await db.refresh(user)
    _set_session_cookies(response, access, refresh)
    return LoginResult(user=UserOut.model_validate(user), next=next_path)


@router.get('/skolstream/login', summary='Перейти ко входу через SkolStream')
async def skolstream_login(
    client: Annotated[SkolstreamClient, Depends(get_skolstream_client)], next: str | None = None
) -> RedirectResponse:
    if not settings.skolstream.enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Вход через SkolStream не настроен')
    state, verifier = new_secret(), new_secret()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    response = RedirectResponse(client.authorize_url(_callback_url(), state, challenge), status_code=302)
    response.set_cookie(
        OAUTH_COOKIE,
        sign_state({'state': state, 'verifier': verifier, 'next': service.safe_next_path(next)}),
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite='lax',
        path='/api/v1/auth/skolstream',
    )
    return response


@router.get('/skolstream/callback', summary='Возврат из SkolStream')
async def skolstream_callback(
    request: Request,
    db: Db,
    client: Annotated[SkolstreamClient, Depends(get_skolstream_client)],
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    app_url = settings.app_url.rstrip('/')
    try:
        saved = read_state(request.cookies.get(OAUTH_COOKIE, ''))
        if not code or not state or saved.get('state') != state:
            raise service.AuthError('Сессия входа устарела')
        token = await client.exchange_code(code, _callback_url(), saved['verifier'])
        profile = await client.fetch_profile(token)
        if not profile.email:
            raise service.AuthError('В профиле SkolStream нет email')
        person = await upsert_person_from_profile(db, profile)
        user = await ensure_user(db, person, profile.email)
        access, refresh = await service.open_session(db, user, 'skolstream', *_client_info(request))
        await db.commit()
    except (TokenError, SkolstreamError, service.AuthError) as exc:
        logger.warning('Вход через SkolStream не удался: %s', exc)
        response = RedirectResponse(f'{app_url}/login?error={quote(str(exc))}', status_code=302)
        response.delete_cookie(OAUTH_COOKIE, path='/api/v1/auth/skolstream')
        return response

    response = RedirectResponse(f'{app_url}{saved["next"]}', status_code=302)
    response.delete_cookie(OAUTH_COOKIE, path='/api/v1/auth/skolstream')
    _set_session_cookies(response, access, refresh)
    return response


@router.post('/refresh', status_code=status.HTTP_204_NO_CONTENT, summary='Продлить сессию')
async def refresh(request: Request, response: Response, db: Db) -> Response:
    token = request.cookies.get(settings.auth.refresh_cookie)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Требуется вход')
    try:
        access, new_refresh = await service.refresh_session(db, token)
    except service.AuthError as exc:
        denied = JSONResponse({'detail': str(exc)}, status_code=status.HTTP_401_UNAUTHORIZED)
        _clear_session_cookies(denied)
        return denied
    await db.commit()
    _set_session_cookies(response, access, new_refresh)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT, summary='Выйти')
async def logout(request: Request, response: Response, db: Db) -> Response:
    await service.close_session(db, request.cookies.get(settings.auth.refresh_cookie))
    await db.commit()
    _clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


async def _judge_mode(db, request: Request, user) -> bool:
    """Интерфейс только для судейства: вход по QR-листу или у пользователя нет других ролей и заявок."""
    if user.is_superuser:
        return False
    token = request.cookies.get(settings.auth.access_cookie) or ''
    try:
        session_id = int(decode_access_token(token)['sid'])
        if await db.scalar(select(AuthSession.method).where(AuthSession.id == session_id)) == 'judge_qr':
            return True
    except (TokenError, KeyError, ValueError):
        pass
    if user.person and user.person.is_employee:
        return False
    roles = set(await db.scalars(select(EventMember.role).where(EventMember.user_id == user.id)))
    if roles != {'judge'}:
        return False
    return not await db.scalar(select(exists().where(Application.user_id == user.id)))


@router.get('/me', response_model=Me, summary='Текущий пользователь')
async def me(request: Request, db: Db, user: CurrentUser) -> Me:
    return Me(user=UserOut.model_validate(user), judge_mode=await _judge_mode(db, request, user))
