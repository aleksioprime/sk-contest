"""
Свои домены лендингов.

Организатор добавляет домен и создаёт у регистратора CNAME на settings.sites_cname_target
(для домена второго уровня — A-запись на тот же IP). Проверка смотрит DNS, после успеха
в динамическую конфигурацию Traefik (coolify-proxy) пишется маршрут: Host → сервис sites,
сертификат Let's Encrypt выпускается автоматически по HTTP-01.
"""

import logging
import re
from pathlib import Path
from typing import Protocol

import dns.asyncresolver
import dns.exception
import dns.resolver

from app.core.config import settings

logger = logging.getLogger('sk_events.domains')

DOMAIN_RE = re.compile(r'^(?=.{4,253}$)(?!-)(?:[a-z0-9-]{1,63}(?<!-)\.)+[a-z]{2,63}$')
BASE_FILE = 'sk-events-sites.yaml'


class DomainError(Exception):
    pass


def normalize_domain(value: str) -> str:
    domain = value.strip().lower()
    domain = re.sub(r'^[a-z]+://', '', domain).split('/')[0].split(':')[0].rstrip('.')
    try:
        domain = domain.encode('idna').decode('ascii')
    except UnicodeError as exc:
        raise DomainError('Некорректное имя домена') from exc
    if not DOMAIN_RE.match(domain):
        raise DomainError('Укажите домен, например konkurs.school.ru')
    base = settings.sites_base_domain.lower()
    if domain == base or domain.endswith(f'.{base}'):
        raise DomainError(f'Поддомен {base} подключается сам, добавлять его не нужно')
    return domain


class DnsChecker(Protocol):
    async def check(self, domain: str) -> str | None:
        """None — домен указывает на нас, иначе текст ошибки для организатора."""


class ResolverChecker:
    def __init__(self, timeout: float = 5.0):
        self.resolver = dns.asyncresolver.Resolver()
        self.resolver.lifetime = timeout

    async def _records(self, name: str, kind: str) -> set[str]:
        try:
            answer = await self.resolver.resolve(name, kind)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            return set()
        return {record.to_text().rstrip('.').lower() for record in answer}

    async def check(self, domain: str) -> str | None:
        target = settings.sites_cname_target.lower()
        try:
            if target in await self._records(domain, 'CNAME'):
                return None
            ours = await self._records(target, 'A')
            theirs = await self._records(domain, 'A')
        except dns.exception.DNSException as exc:
            return f'DNS не отвечает: {exc.__class__.__name__}. Попробуйте позже'
        if not theirs:
            return f'Для {domain} нет записи. Создайте CNAME на {target}'
        if ours and theirs <= ours:
            return None
        return f'{domain} указывает не на SK Events ({", ".join(sorted(theirs))}). Нужен CNAME на {target}'


_checker = ResolverChecker()


def get_dns_checker() -> DnsChecker:
    return _checker


# --- Динамическая конфигурация Traefik -----------------------------------------------------------


def _dir() -> Path | None:
    return Path(settings.traefik_dynamic_dir) if settings.traefik_dynamic_dir else None


def _route_name(domain: str) -> str:
    return 'sk-events-' + re.sub(r'[^a-z0-9]+', '-', domain)


def _file(domain: str) -> str:
    return f'{_route_name(domain)}.yaml'


def base_config() -> str:
    return (
        'http:\n'
        '  middlewares:\n'
        '    sk-events-https:\n'
        '      redirectScheme:\n'
        '        scheme: https\n'
        '  services:\n'
        '    sk-events-sites:\n'
        '      loadBalancer:\n'
        '        servers:\n'
        f'          - url: "{settings.sites_upstream_url}"\n'
    )


def route_config(domain: str) -> str:
    name = _route_name(domain)
    return (
        'http:\n'
        '  routers:\n'
        f'    {name}:\n'
        f'      rule: "Host(`{domain}`)"\n'
        '      entryPoints: [https]\n'
        '      service: sk-events-sites\n'
        '      tls:\n'
        f'        certResolver: {settings.traefik_certresolver}\n'
        f'    {name}-http:\n'
        f'      rule: "Host(`{domain}`)"\n'
        '      entryPoints: [http]\n'
        '      middlewares: [sk-events-https]\n'
        '      service: sk-events-sites\n'
    )


def write_route(domain: str) -> bool:
    directory = _dir()
    if directory is None:
        logger.info('TRAEFIK_DYNAMIC_DIR не задан, маршрут для %s не записан', domain)
        return False
    directory.mkdir(parents=True, exist_ok=True)
    (directory / BASE_FILE).write_text(base_config())
    # Пишем во временный файл и переименовываем: Traefik не прочитает файл наполовину
    tmp = directory / f'.{_file(domain)}.tmp'
    tmp.write_text(route_config(domain))
    tmp.replace(directory / _file(domain))
    return True


def remove_route(domain: str) -> None:
    directory = _dir()
    if directory is not None:
        (directory / _file(domain)).unlink(missing_ok=True)
