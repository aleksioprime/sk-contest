# Домены и сертификаты

| Адрес | Что | Сертификат |
|---|---|---|
| `app.events.skolhub.ru` | приложение и API | обычный, HTTP-01 |
| `events.skolhub.ru/<slug>` | лендинг по пути | обычный, HTTP-01 |
| `<slug>.events.skolhub.ru` | лендинг на поддомене | один wildcard, DNS-01 |
| свой домен организатора | лендинг | на каждый домен, HTTP-01 |

Сервис `sites` определяет сайт по заголовку `Host` (`sites/lib/resolve-site.js`), данные берёт из
`/api/v1/public/sites/by-slug/<slug>` или `/by-domain/<domain>`. Ответы API кэшируются в Redis на 2 минуты
и сбрасываются при публикации сайта, итогов и изменении доменов.

## Поддомены `*.events.skolhub.ru`

1. DNS у REG.RU: `events` и `*.events` — A-записи на IP сервера Coolify, `sites.events` — тоже (на него организаторы делают CNAME).
2. Wildcard-сертификат выпускается только через DNS-01. В Coolify: *Servers → Proxy* — добавить к Traefik
   резолвер с провайдером `regru` и переменные `REGRU_USERNAME`, `REGRU_PASSWORD`
   (у REG.RU нужно включить доступ к API и разрешить IP сервера):

   ```yaml
   command:
     - '--certificatesresolvers.letsencrypt-dns.acme.dnschallenge.provider=regru'
     - '--certificatesresolvers.letsencrypt-dns.acme.email=<почта администратора>'
     - '--certificatesresolvers.letsencrypt-dns.acme.storage=/traefik/acme-dns.json'
   environment:
     - REGRU_USERNAME=<логин>
     - REGRU_PASSWORD=<пароль API>
   ```

3. У сервиса `sites` в Coolify домены `https://events.skolhub.ru,https://*.events.skolhub.ru`, для wildcard —
   резолвер `letsencrypt-dns`.

## Свои домены

Организатор в конструкторе (вкладка «Адрес») добавляет домен и создаёт у своего регистратора
`CNAME` на `sites.events.skolhub.ru` (для домена второго уровня — A-запись на тот же IP).

1. API проверяет DNS (`app/modules/sites/domains.py`): CNAME на `SITES_CNAME_TARGET` или те же A-записи.
2. При первой успешной проверке в каталог `TRAEFIK_DYNAMIC_DIR` пишутся два файла:
   `sk-events-sites.yaml` (сервис `sites` и редирект на HTTPS) и `sk-events-<домен>.yaml` (маршруты домена).
   Traefik подхватывает их сам и выпускает сертификат по HTTP-01.
3. Ожидающие домены воркер перепроверяет каждые 10 минут в течение недели. Отключение домена удаляет его файл.

Переменные backend и worker:

| Переменная | Значение в проде |
|---|---|
| `SITES_CNAME_TARGET` | `sites.events.skolhub.ru` |
| `SITES_UPSTREAM_URL` | адрес контейнера `sites` в сети Coolify, например `http://sites-<uuid>:3000` |
| `TRAEFIK_DYNAMIC_DIR` | `/traefik-dynamic` — смонтированный `/data/coolify/proxy/dynamic` |
| `TRAEFIK_CERTRESOLVER` | `letsencrypt` |

Каталог `/data/coolify/proxy/dynamic` принадлежит root, а backend в образе работает от пользователя с UID 1001:
выдайте ему право записи (`setfacl -m u:1001:rwx /data/coolify/proxy/dynamic`). Пустой `TRAEFIK_DYNAMIC_DIR`
отключает запись маршрутов — так работает локальная разработка.
