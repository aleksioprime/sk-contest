"""Устойчивость фонового воркера к обрывам соединения с Redis."""

import asyncio
import socket
import struct
from dataclasses import replace

import pytest
from arq.connections import create_pool
from redis.exceptions import ConnectionError as RedisConnectionError

from app.workers.main import WorkerSettings

COMMANDS = 8


async def _pipe(reader, writer) -> None:
    """Пересылает данные, пока одна из сторон не закроет соединение."""
    try:
        while data := await reader.read(4096):
            writer.write(data)
            await writer.drain()
    except OSError:
        pass
    finally:
        writer.close()


class ResettingProxy:
    """Прокси к Redis: сбрасывает первое соединение через RST после нескольких команд, как при выкатке."""

    def __init__(self, host: str, port: int) -> None:
        self.upstream = (host, port)
        self.connections = 0
        self.tasks: set[asyncio.Task] = set()

    async def _handle(self, reader, writer) -> None:
        self.connections += 1
        first = self.connections == 1
        up_reader, up_writer = await asyncio.open_connection(*self.upstream)
        self.tasks.add(asyncio.create_task(_pipe(up_reader, writer)))
        commands = 0
        try:
            while data := await reader.read(4096):
                commands += 1
                if first and commands > 3:
                    linger = struct.pack('ii', 1, 0)
                    writer.get_extra_info('socket').setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
                    writer.transport.abort()
                    return
                up_writer.write(data)
                await up_writer.drain()
        except OSError:
            pass
        finally:
            up_writer.close()

    async def run_commands(self, settings) -> None:
        """Выполняет те же запросы, что воркер делает при опросе очереди."""
        server = await asyncio.start_server(self._handle, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        pool = await create_pool(replace(settings, host='127.0.0.1', port=port, conn_retries=0))
        try:
            for _ in range(COMMANDS):
                await pool.zrangebyscore('arq:test-queue', 0, 1)
        finally:
            await pool.aclose()
            server.close()
            for task in self.tasks:
                task.cancel()


def _proxy() -> ResettingProxy:
    settings = WorkerSettings.redis_settings
    return ResettingProxy(settings.host, settings.port)


async def test_worker_survives_connection_reset():
    proxy = _proxy()
    await asyncio.wait_for(proxy.run_commands(WorkerSettings.redis_settings), 30)
    assert proxy.connections >= 2


async def test_without_retries_connection_reset_is_fatal():
    with pytest.raises(RedisConnectionError):
        await asyncio.wait_for(
            _proxy().run_commands(replace(WorkerSettings.redis_settings, retry=None, retry_on_error=None)), 30
        )
