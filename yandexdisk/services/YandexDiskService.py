from typing import Optional, Dict, List

import requests
from django.core.cache import cache
from django.http import HttpRequest


class YandexDiskService:
    """Service for interaction with Yandex.Disk API."""

    TOKEN_URL = 'https://oauth.yandex.ru/token'
    PUBLIC_RESOURCES_URL = 'https://cloud-api.yandex.net/v1/disk/public/resources'

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def get_token(self, code: str) -> Optional[str]:
        """Get an access token."""
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        try:
            response = requests.post(self.TOKEN_URL, data=data)
            response.raise_for_status()
            token = response.json().get('access_token', None)
            if isinstance(token, str):
                return token
            return None
        except requests.RequestException:
            return None

    def get_public_resources(self, token: str, public_key: str) -> Optional[List[Dict]]:
        """Gets a list of public resources by public_key."""
        cache_key = self._generate_cache_key(public_key)
        cached_resources = cache.get(cache_key)
        if cached_resources is not None:
            return cached_resources

        headers = {'Authorization': f'OAuth {token}'}
        params = self._build_public_resources_params(public_key)

        try:
            response = requests.get(self.PUBLIC_RESOURCES_URL, headers=headers, params=params)
            response.raise_for_status()
            resources = self._parse_public_resources(response.json())
            cache.set(cache_key, resources, timeout=300)
            return resources
        except requests.RequestException:
            return None

    @staticmethod
    def _generate_cache_key(public_key: str) -> str:
        """Generates a key for the cache."""
        return f"public_resources_{public_key}"

    @staticmethod
    def _build_public_resources_params(public_key: str) -> Dict[str, str]:
        """Builds query parameters for retrieving public resources."""
        return {
            'public_key': public_key,
            'fields': (
                '_embedded.items.name,_embedded.items.type,_embedded.items.path,'
                '_embedded.items.mime_type,_embedded.items.file'
            ),
        }

    @staticmethod
    def _parse_public_resources(data: Dict) -> List[Dict]:
        """Parses the API response and retrieves resources."""
        if '_embedded' in data and 'items' in data['_embedded']:
            return data['_embedded']['items']
        elif data.get('type') == 'file':
            return [data]
        else:
            return []

    @staticmethod
    def get_yandex_disk_token(request: HttpRequest) -> Optional[str]:
        """Gets a token from a session."""
        return request.session.get('yandex_disk_token')