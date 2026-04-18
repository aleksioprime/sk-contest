import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException

from src.core.config import settings

logger = logging.getLogger('sk_contest')


class NocoBaseClient:
    @staticmethod
    def _as_record(payload: Any) -> dict:
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    return item
        return {}

    def _serialize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        serialized = {}
        for key, value in params.items():
            if isinstance(value, (dict, list)):
                serialized[key] = json.dumps(value)
            else:
                serialized[key] = value
        return serialized

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: Any = None,
    ) -> Any:
        if not settings.nocobase_api_key:
            raise HTTPException(status_code=500, detail='NOCOBASE_API_KEY is not configured')

        headers = {
            'Authorization': f'Bearer {settings.nocobase_api_key}',
            'Content-Type': 'application/json',
        }

        safe_params = self._serialize_params(params) if params else None

        async with httpx.AsyncClient(
            base_url=settings.nocobase_api_url,
            timeout=settings.nocobase_timeout,
            headers=headers,
            trust_env=False,
        ) as client:
            response = await client.request(
                method,
                path,
                params=safe_params,
                json=json_payload,
            )

        if response.status_code >= 400:
            logger.error('NocoBase %s %s → %s: %s', method, path, response.status_code, response.text)
            raise HTTPException(status_code=response.status_code, detail=f'NocoBase error: {response.text}')

        data = response.json()
        return data.get('data', data)

    async def list(self, collection: str, **params) -> list[dict]:
        return await self._request('GET', f'/{collection}:list', params=params)

    async def get(self, collection: str, filter: dict | None = None, **params) -> dict | None:
        request_params = {**params}
        if filter:
            request_params['filter'] = filter
        result = await self._request('GET', f'/{collection}:list', params=request_params)

        if isinstance(result, list):
            return result[0] if result else None
        if isinstance(result, dict) and 'data' in result:
            items = result['data']
            return items[0] if items else None
        return result if isinstance(result, dict) else None

    async def get_by_id(self, collection: str, record_id: int | str, **params) -> dict:
        result = await self._request('GET', f'/{collection}:get', params={'filterByTk': record_id, **params})
        return self._as_record(result)

    async def create(self, collection: str, data: dict) -> dict:
        result = await self._request('POST', f'/{collection}:create', json_payload=data)
        return self._as_record(result)

    async def update(self, collection: str, record_id: int | str, data: dict) -> dict:
        result = await self._request(
            'POST',
            f'/{collection}:update',
            params={'filterByTk': record_id},
            json_payload=data,
        )
        return self._as_record(result)


nocobase = NocoBaseClient()
