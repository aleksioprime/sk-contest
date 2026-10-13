async def test_health(client):
    response = await client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


async def test_meta(client):
    response = await client.get('/api/v1/meta')
    assert response.status_code == 200
    body = response.json()
    assert body['name'] == 'SK Events'
    assert body['sites_base_domain'] == 'events.skolhub.ru'


async def test_ready_reports_each_dependency(client):
    response = await client.get('/api/health/ready')
    assert response.status_code in (200, 503)
    assert set(response.json()['checks']) == {'database', 'redis'}
