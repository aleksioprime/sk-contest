import pytest

from app.core.config import settings
from app.modules.sites.domains import get_dns_checker
from tests.test_applications import SLUG, _open_event

pytestmark = pytest.mark.usefixtures('redis_clean')


def _content(image_url: str, **overrides) -> dict:
    blocks = [
        {'id': 'h1', 'type': 'header', 'variant': 'sticky', 'props': {'title': 'SkolStart', 'showCta': True}},
        {
            'id': 'b1',
            'type': 'hero',
            'variant': 'image-right',
            'props': {'title': 'SkolStart 2027', 'image': {'file_id': None, 'url': image_url, 'alt': ''}},
            'common': {'anchor': 'top', 'menuTitle': '', 'background': 'default', 'visibility': 'always'},
        },
        {
            'id': 'b2',
            'type': 'text',
            'variant': 'single',
            'props': {
                'title': 'О конкурсе',
                'body': '<p onclick="x()">Текст<script>alert(1)</script></p><a href="javascript:1">ссылка</a>',
            },
            'common': {'anchor': 'about', 'menuTitle': 'О конкурсе'},
        },
        {
            'id': 'b3',
            'type': 'faq',
            'variant': 'default',
            'props': {'title': 'Вопросы', 'items': [{'question': 'Кто?', 'answer': 'Все'}]},
        },
    ]
    return {
        'theme': {'accent': '#0f6e56', 'fontPair': 'manrope', 'mode': 'light'},
        'pages': [{'path': '', 'title': 'Главная', 'blocks': blocks}],
        'seo': {'title': 'SkolStart 2027', 'description': 'Конкурс проектов', 'metrika': '12345'},
        **overrides,
    }


async def _image(client) -> str:
    uploaded = await client.post(
        '/api/v1/files', files={'file': ('cover.png', b'\x89PNG\r\n\x1a\nfake', 'image/png')}, data={'purpose': 'image'}
    )
    assert uploaded.status_code == 201, uploaded.text
    return uploaded.json()['url']


async def test_draft_publish_and_public_site(db, client):
    event = await _open_event(db, client)
    url = f'/api/v1/events/{event["id"]}/site'
    assert (await client.get(url)).json()['exists'] is False

    # без опубликованного сайта лендинг строится по шаблону: content = null, данные мероприятия есть
    public = (await client.get(f'/api/v1/public/sites/by-slug/{SLUG}')).json()
    assert public['content'] is None and public['event']['title'] == 'SkolStart'
    assert public['stats']['directions'] == 1
    assert public['event']['directions'][0]['title'] == 'Инженерия'
    assert public['event']['stages'][0]['title'] and public['event']['stages'][0]['kind'] in ('remote', 'onsite')

    saved = await client.put(url, json={'content': _content(await _image(client))})
    assert saved.status_code == 200, saved.text
    site = saved.json()
    body = site['draft']['pages'][0]['blocks'][2]['props']['body']
    assert '<script' not in body and 'onclick' not in body and 'javascript' not in body
    assert 'Текст' in body
    assert site['has_unpublished_changes'] is True
    assert site['urls'][0] == f'https://{SLUG}.{settings.sites_base_domain}'

    published = (await client.post(f'{url}/publish', json={'note': 'Первая версия'})).json()
    assert published['published_version'] == 1 and published['has_unpublished_changes'] is False
    public = (await client.get(f'/api/v1/public/sites/by-slug/{SLUG}')).json()
    assert public['content']['seo']['metrika'] == '12345'

    # правка черновика не меняет опубликованный сайт, пока не опубликуют
    changed = _content(await _image(client))
    changed['pages'][0]['blocks'][1]['props']['title'] = 'Новый заголовок'
    await client.put(url, json={'content': changed})
    await client.post(f'{url}/publish', json={})
    versions = (await client.get(f'{url}/versions')).json()
    assert [(v['number'], v['published']) for v in versions] == [(2, True), (1, False)]
    restored = (await client.post(f'{url}/versions/{versions[1]["id"]}/restore')).json()
    assert restored['draft']['pages'][0]['blocks'][1]['props']['title'] == 'SkolStart 2027'
    assert restored['published_version'] == 2 and restored['has_unpublished_changes'] is True

    await client.post(f'{url}/unpublish')
    assert (await client.get(f'/api/v1/public/sites/by-slug/{SLUG}')).json()['content'] is None


async def test_invalid_content_is_rejected(db, client):
    event = await _open_event(db, client)
    url = f'/api/v1/events/{event["id"]}/site'
    image = await _image(client)

    bad = _content(image)
    bad['pages'][0]['blocks'].append({'id': 'x', 'type': 'marquee', 'variant': 'default', 'props': {}})
    bad['pages'][0]['blocks'][1]['variant'] = 'fullscreen'
    bad['pages'][0]['blocks'][0]['props']['extra'] = 1
    response = await client.put(url, json={'content': bad})
    assert response.status_code == 422
    where = {e['where'] for e in response.json()['detail']['errors']}
    assert {'pages.0.blocks.4', 'pages.0.blocks.1', 'pages.0.blocks.0.props'} <= where

    foreign = _content('https://tracker.example/pixel.png')
    assert (await client.put(url, json={'content': foreign})).status_code == 422

    js = _content(image)
    js['pages'][0]['blocks'][1]['props']['ctaHref'] = 'javascript:alert(1)'
    assert (await client.put(url, json={'content': js})).status_code == 422

    private = await client.post('/api/v1/files', files={'file': ('a.pdf', b'%PDF-1.4', 'application/pdf')})
    hidden = _content(f'/api/v1/public/files/{private.json()["id"]}')
    assert (await client.put(url, json={'content': hidden})).status_code == 400


class _Dns:
    def __init__(self):
        self.answer: str | None = 'Для konkurs.school.ru нет записи'

    async def check(self, domain):
        return self.answer


async def test_custom_domain(db, client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'traefik_dynamic_dir', str(tmp_path))
    dns = _Dns()
    client._transport.app.dependency_overrides[get_dns_checker] = lambda: dns
    event = await _open_event(db, client)
    url = f'/api/v1/events/{event["id"]}/site'
    await client.put(url, json={'content': _content(await _image(client))})
    await client.post(f'{url}/publish', json={})

    assert (await client.post(f'{url}/domains', json={'domain': f'x.{settings.sites_base_domain}'})).status_code == 400
    site = (await client.post(f'{url}/domains', json={'domain': 'https://Konkurs.School.ru/'})).json()
    domain = site['domains'][0]
    assert domain['domain'] == 'konkurs.school.ru' and domain['status'] == 'pending'
    assert (await client.get('/api/v1/public/sites/by-domain/konkurs.school.ru')).status_code == 404

    dns.answer = None
    site = (await client.post(f'/api/v1/site-domains/{domain["id"]}/check')).json()
    assert site['domains'][0]['status'] == 'active'
    assert site['urls'][0] == 'https://konkurs.school.ru'
    route = (tmp_path / 'sk-events-konkurs-school-ru.yaml').read_text()
    assert 'Host(`konkurs.school.ru`)' in route and 'certResolver' in route
    assert (tmp_path / 'sk-events-sites.yaml').exists()

    public = (await client.get('/api/v1/public/sites/by-domain/konkurs.school.ru')).json()
    assert public['event']['slug'] == SLUG and public['domain'] == 'konkurs.school.ru'

    await client.delete(f'/api/v1/site-domains/{domain["id"]}')
    assert not (tmp_path / 'sk-events-konkurs-school-ru.yaml').exists()
