import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger('sk_events')


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        if request.url.path not in ('/api/health', '/api/health/ready'):
            logger.info('%s %s → %s (%.0f ms)', request.method, request.url.path, response.status_code, elapsed)
        return response
