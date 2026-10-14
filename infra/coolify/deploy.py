"""
Развёртывание SK Events в Coolify через API.

    python3 infra/coolify/deploy.py            # создать ресурс (если нет), обновить переменные и домены, запустить сборку
    python3 infra/coolify/deploy.py --dry-run  # показать, что будет сделано

Берёт COOLIFY_URL, COOLIFY_API_TOKEN и переменные приложения из .env.prod.
Ресурс создаётся в проекте Events; сервер — тот же, что у старого приложения «contest» (LEGACY_APP).
Репозиторий публичный, сборка из ветки main.
Только стандартная библиотека Python.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_APP = 'xbzrf3pmtpyslst9d29fuy68'
NAME = 'sk-events'
PROJECT = 'Events'
COMPOSE = '/infra/coolify/docker-compose.prod.yaml'
DOMAINS = {
    'frontend': 'https://app.events.skolhub.ru',
    'sites': 'https://events.skolhub.ru',
}
# Переменные из .env.prod, которые передаются в Coolify (остальные строки файла — старое приложение и служебные)
APP_VARS = [
    'SECRET_KEY',
    'DB__PASSWORD',
    'BOOTSTRAP_ADMIN_EMAILS',
    'BOOTSTRAP_ADMIN_PASSWORD',
    'SMTP__USER',
    'SMTP__PASSWORD',
    'CAPTCHA__CLIENT_KEY',
    'CAPTCHA__SERVER_KEY',
    'TRAEFIK_DYNAMIC_DIR',
]


def read_env(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip()
    return env


class Coolify:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip('/') + '/api/v1'
        self.token = token

    def call(self, method: str, path: str, body: dict | list | None = None, allow_error: bool = False):
        request = urllib.request.Request(
            self.url + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json', 'Accept': 'application/json'},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                text = response.read().decode()
        except urllib.error.HTTPError as exc:
            if allow_error:
                return None
            sys.exit(f'{method} {path}: {exc.code} {exc.read().decode()[:500]}')
        return json.loads(text) if text else None


def main() -> None:
    dry = '--dry-run' in sys.argv
    env = read_env(ROOT / '.env.prod')
    missing = [k for k in ('COOLIFY_URL', 'COOLIFY_API_TOKEN', 'SECRET_KEY', 'DB__PASSWORD') if not env.get(k)]
    if missing:
        sys.exit(f'Заполните в .env.prod: {", ".join(missing)}')
    api = Coolify(env['COOLIFY_URL'], env['COOLIFY_API_TOKEN'])

    project = next((p for p in api.call('GET', '/projects') if p['name'] == PROJECT), None)
    if project is None:
        sys.exit(f'Создайте в Coolify проект {PROJECT}')
    legacy = api.call('GET', f'/applications/{LEGACY_APP}')  # сервер и destination — как у старого приложения
    apps = api.call('GET', '/applications')
    app = next((a for a in apps if a.get('name') == NAME), None)

    if app is None:
        body = {
            'project_uuid': project['uuid'],
            'environment_name': 'production',
            'server_uuid': legacy['destination']['server']['uuid'],
            'destination_uuid': legacy['destination']['uuid'],
            'git_repository': f'https://github.com/{legacy["git_repository"]}',
            'git_branch': 'main',
            'build_pack': 'dockercompose',
            'docker_compose_location': COMPOSE,
            'ports_exposes': '80',
            'name': NAME,
            'description': 'SK Events: мероприятия, заявки, оценивание, лендинги',
            'instant_deploy': False,
        }
        print('Создаю ресурс', json.dumps({k: v for k, v in body.items() if 'uuid' not in k}, ensure_ascii=False))
        if dry:
            return
        app = api.call('POST', '/applications/public', body)
    uuid = app['uuid']
    print('Ресурс', uuid)

    # is_literal: значения с $ передаются как есть, без подстановки переменных
    variables = [{'key': k, 'value': env[k], 'is_preview': False, 'is_literal': True} for k in APP_VARS if env.get(k)]
    print('Переменные:', ', '.join(v['key'] for v in variables))
    domains = [{'name': service, 'domain': domain} for service, domain in DOMAINS.items()]
    print('Домены:', domains)
    if dry:
        return
    api.call('PATCH', f'/applications/{uuid}/envs/bulk', {'data': variables})
    # Домены Coolify принимает только после того, как прочитал compose из репозитория (первая сборка)
    if api.call('PATCH', f'/applications/{uuid}', {'docker_compose_domains': domains}, allow_error=True) is None:
        print('Compose ещё не загружен: после этой сборки запустите скрипт ещё раз, чтобы назначить домены')
    deployment = api.call('POST', f'/deploy?uuid={uuid}&force=false')
    print('Сборка запущена:', json.dumps(deployment, ensure_ascii=False))


if __name__ == '__main__':
    main()
