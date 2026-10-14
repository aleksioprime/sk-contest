"""
Проверка содержимого сайта перед сохранением.

Структура (тема, страницы, SEO) — Pydantic. Props блоков — JSON Schema из packages/blocks
(block_schemas.json генерируется командой `npm run schema --workspace packages/blocks`).
Форматированный текст очищается по списку разрешённых тегов, картинки и файлы — только наши публичные файлы.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any, Literal

import nh3
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, ValidationError, field_validator

SCHEMAS_FILE = Path(__file__).with_name('block_schemas.json')
ASSET_URL = re.compile(r'^/api/v1/public/files/(\d+)$')
ANCHOR = r'^[a-z0-9][a-z0-9-]{0,39}$'

RICH_TAGS = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'a', 'ul', 'ol', 'li', 'h3', 'h4', 'blockquote'}
RICH_ATTRIBUTES = {'a': {'href', 'target'}}


class ContentError(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__('; '.join(f'{e["where"]}: {e["message"]}' for e in errors[:5]))


@cache
def block_schemas() -> dict[str, Any]:
    return json.loads(SCHEMAS_FILE.read_text())['blocks']


@cache
def _validator(block_type: str) -> Draft202012Validator:
    return Draft202012Validator(block_schemas()[block_type])


def sanitize_html(html: str) -> str:
    return nh3.clean(
        html,
        tags=RICH_TAGS,
        attributes=RICH_ATTRIBUTES,
        url_schemes={'http', 'https', 'mailto', 'tel'},
        link_rel='noopener noreferrer',
    ).strip()


class Asset(BaseModel):
    file_id: int | None = None
    url: str = Field(max_length=500)
    alt: str = Field(default='', max_length=300)
    name: str = Field(default='', max_length=255)

    @field_validator('url')
    @classmethod
    def own_file(cls, value: str) -> str:
        if not ASSET_URL.match(value):
            raise ValueError('Файл должен быть загружен в SK Events')
        return value


class Theme(BaseModel):
    preset: str = Field(default='violet', max_length=20)
    accent: str = Field(default='#534ab7', pattern=r'^#[0-9a-fA-F]{6}$')
    fontPair: Literal['golos', 'unbounded', 'manrope', 'serif'] = 'golos'  # noqa: N815 — как в packages/blocks
    radius: Literal['sharp', 'soft', 'round'] = 'soft'
    mode: Literal['light', 'dark'] = 'light'
    logo: Asset | None = None
    favicon: Asset | None = None


class Common(BaseModel):
    anchor: str = Field(default='', pattern=rf'{ANCHOR}|^$')
    menuTitle: str = Field(default='', max_length=40)  # noqa: N815
    background: Literal['default', 'muted', 'accent'] = 'default'
    visibility: Literal['always', 'registration', 'results'] = 'always'


class Block(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r'^[A-Za-z0-9_-]+$')
    type: str = Field(max_length=40)
    variant: str = Field(max_length=40)
    hidden: bool = False
    props: dict[str, Any] = {}
    common: Common = Common()


class Page(BaseModel):
    path: str = Field(default='', pattern=rf'{ANCHOR}|^$')
    title: str = Field(default='Главная', max_length=80)
    blocks: list[Block] = Field(default=[], max_length=60)


class Seo(BaseModel):
    title: str = Field(default='', max_length=120)
    description: str = Field(default='', max_length=300)
    image: Asset | None = None
    metrika: str = Field(default='', pattern=r'^\d{0,12}$')


class SiteContent(BaseModel):
    theme: Theme = Theme()
    pages: list[Page] = Field(min_length=1, max_length=10)
    seo: Seo = Seo()


def _clean_props(schema: dict, value: Any, where: str, errors: list[dict], files: set[int]) -> Any:
    """Очистка по схеме: HTML в richtext, проверка ссылок на файлы. Структура уже проверена JSON Schema."""
    if value is None:
        return None
    if schema.get('x-richtext'):
        return sanitize_html(value)
    if schema.get('type') == 'array':
        return [_clean_props(schema['items'], item, f'{where}.{i}', errors, files) for i, item in enumerate(value)]
    if 'file_id' in schema.get('properties', {}) and isinstance(value, dict):
        match = ASSET_URL.match(value.get('url', ''))
        if not match:
            errors.append({'where': where, 'message': 'Файл должен быть загружен в SK Events'})
            return value
        files.add(int(match.group(1)))
        return value
    if isinstance(schema.get('properties'), dict) and isinstance(value, dict):
        return {
            key: _clean_props(schema['properties'][key], item, f'{where}.{key}', errors, files)
            for key, item in value.items()
        }
    return value


def validate_content(raw: dict) -> tuple[dict, set[int]]:
    """Проверенное и очищенное содержимое сайта и id файлов, на которые оно ссылается."""
    try:
        content = SiteContent.model_validate(raw)
    except ValidationError as exc:
        raise ContentError(
            [{'where': '.'.join(str(p) for p in e['loc']), 'message': e['msg']} for e in exc.errors()]
        ) from exc

    errors: list[dict] = []
    files: set[int] = set()
    schemas = block_schemas()
    paths = set()
    for p_index, page in enumerate(content.pages):
        if page.path in paths:
            errors.append({'where': f'pages.{p_index}.path', 'message': 'Адрес страницы повторяется'})
        paths.add(page.path)
        ids = set()
        for b_index, block in enumerate(page.blocks):
            where = f'pages.{p_index}.blocks.{b_index}'
            schema = schemas.get(block.type)
            if schema is None:
                errors.append({'where': where, 'message': f'Неизвестный блок {block.type}'})
                continue
            if block.id in ids:
                errors.append({'where': where, 'message': 'Повторяется id блока'})
            ids.add(block.id)
            if block.variant not in schema['x-variants']:
                errors.append({'where': where, 'message': f'Неизвестный вариант {block.variant}'})
            problems = sorted(_validator(block.type).iter_errors(block.props), key=lambda e: list(e.path))
            for problem in problems[:5]:
                field = '.'.join(str(p) for p in problem.path)
                errors.append({'where': f'{where}.props{"." + field if field else ""}', 'message': problem.message})
            if not problems:
                block.props = _clean_props(schema, block.props, f'{where}.props', errors, files)

    for asset in (content.theme.logo, content.theme.favicon, content.seo.image):
        if asset:
            files.add(int(ASSET_URL.match(asset.url).group(1)))
    if errors:
        raise ContentError(errors)
    return content.model_dump(), files
