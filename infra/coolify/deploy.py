"""
Развёртывание SK Events в Coolify через API.

    python3 infra/coolify/deploy.py            # создать ресурс (если нет), обновить переменные и домены, запустить сборку
    python3 infra/coolify/deploy.py --dry-run  # показать, что будет сделано

Берёт COOLIFY_URL, COOLIFY_API_TOKEN и переменные приложения из .env.prod.
Проект, окружение, сервер и источник GitHub — те же, что у старого приложения «contest» (LEGACY_APP).
Только стандартная библиотека Python.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_APP = 'xbzrf3pmtpyslst9d29fuy68'
NAME = 'sk-events'
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
    'NOCOBASE_URL',
    'NOCOBASE_API_KEY',
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

    def call(self, method: str, path: str, body: dict | list | None = None):
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
            sys.exit(f'{method} {path}: {exc.code} {exc.read().decode()[:500]}')
        return json.loads(text) if text else None


def main() -> None:
    dry = '--dry-run' in sys.argv
    env = read_env(ROOT / '.env.prod')
    missing = [k for k in ('COOLIFY_URL', 'COOLIFY_API_TOKEN', 'SECRET_KEY', 'DB__PASSWORD') if not env.get(k)]
    if missing:
        sys.exit(f'Заполните в .env.prod: {", ".join(missing)}')
    api = Coolify(env['COOLIFY_URL'], env['COOLIFY_API_TOKEN'])

    legacy = api.call('GET', f'/applications/{LEGACY_APP}')
    environment = api.call('GET', '/environments/' + str(legacy['environment_id'])) if 'environment_id' in legacy else None
    apps = api.call('GET', '/applications')
    app = next((a for a in apps if a.get('name') == NAME), None)

    if app is None:
        body = {
            'project_uuid': legacy.get('project_uuid') or (environment or {}).get('project_uuid'),
            'environment_name': (environment or {}).get('name', 'production'),
            'server_uuid': legacy['destination']['server']['uuid'],
            'destination_uuid': legacy['destination']['uuid'],
            'github_app_uuid': legacy['source']['uuid'],
            'git_repository': legacy['git_repository'],
            'git_branch': 'main',
            'build_pack': 'dockercompose',
            'docker_compose_location': COMPOSE,
            'name': NAME,
            'description': 'SK Events: мероприятия, заявки, оценивание, лендинги',
            'instant_deploy': False,
            'ports_exposes': '80',
        }
        print('Создаю ресурс', json.dumps({k: v for k, v in body.items() if 'uuid' not in k}, ensure_ascii=False))
        if dry:
            return
        app = api.call('POST', '/applications/private-github-app', body)
    uuid = app['uuid']

    variables = [{'key': k, 'value': env.get(k, ''), 'is_preview': False} for k in APP_VARS if k in env]
    print('Переменные:', ', '.join(v['key'] for v in variables))
    domains = [{'name': service, 'domain': domain} for service, domain in DOMAINS.items()]
    print('Домены:', domains)
    if dry:
        return
    api.call('PATCH', f'/applications/{uuid}/envs/bulk', {'data': variables})
    api.call('PATCH', f'/applications/{uuid}', {'docker_compose_domains': domains})
    deployment = api.call('POST', f'/deploy?uuid={uuid}&force=false')
    print('Сборка запущена:', json.dumps(deployment, ensure_ascii=False))


if __name__ == '__main__':
    main()
