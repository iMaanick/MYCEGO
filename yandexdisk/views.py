import io
import zipfile
from typing import List, Dict, Optional

from urllib.parse import urlparse, parse_qs

import requests
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpRequest
from django.urls import reverse
from django.views import View

from .forms import AuthForm, TokenForm, PublicLinkForm, FileType
from .services.YandexDiskService import YandexDiskService


class AuthUrlView(View):
    """View for handling authorization URLs."""

    template_name = 'disk/auth_url.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        form = AuthForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = AuthForm(request.POST)
        if form.is_valid():
            client_id = form.cleaned_data['client_id']
            client_secret = form.cleaned_data['client_secret']
            self._save_credentials_to_session(request, client_id, client_secret)
            return redirect(reverse('auth_token'))
        return render(request, self.template_name, {'form': form})

    @staticmethod
    def _save_credentials_to_session(request: HttpRequest, client_id: str, client_secret: str) -> None:
        """Save the client ID and secret in the session."""
        request.session['client_id'] = client_id
        request.session['client_secret'] = client_secret


class AuthTokenView(View):
    """A view for exchanging an authorization code for a token."""

    template_name = 'disk/auth_token.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        form = TokenForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = TokenForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            client_id = request.session.get('client_id')
            client_secret = request.session.get('client_secret')

            if not self._has_credentials(client_id, client_secret):
                return redirect(reverse('auth_url'))

            yandex_service = YandexDiskService(client_id, client_secret)
            token = yandex_service.get_token(code)

            if token:
                request.session['yandex_disk_token'] = token
                return redirect(reverse('home'))
            else:
                form.add_error(None, 'Ошибка получения токена')
        return render(request, self.template_name, {'form': form})

    @staticmethod
    def _has_credentials(client_id: Optional[str], client_secret: Optional[str]) -> bool:
        """Checks if there is a client_id and client_secret."""
        return bool(client_id and client_secret)


class HomeView(View):
    """View for displaying files from a public link."""

    template_name = 'disk/home.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        token = YandexDiskService.get_yandex_disk_token(request)
        if not token:
            return redirect(reverse('auth_url'))
        form = PublicLinkForm()
        return render(request, self.template_name, {'form': form, 'files': []})

    def post(self, request: HttpRequest) -> HttpResponse:
        token = YandexDiskService.get_yandex_disk_token(request)
        if not token:
            return redirect(reverse('auth_url'))

        form = PublicLinkForm(request.POST)
        files = []

        if form.is_valid():
            public_key = form.cleaned_data['public_key']
            file_type = form.cleaned_data.get('file_type', 'all')

            yandex_service = YandexDiskService(
                client_id=request.session.get('client_id', ''),
                client_secret=request.session.get('client_secret', '')
            )
            resources = yandex_service.get_public_resources(token, public_key)

            if resources is not None:
                files = self._filter_files(resources, file_type)
            else:
                form.add_error(None, 'Ошибка получения данных с Яндекс.Диска')

        return render(request, self.template_name, {'form': form, 'files': files})

    @staticmethod
    def _filter_files(files: List[Dict], file_type: str) -> List[Dict]:
        """Filters files by type."""
        if file_type == FileType.ALL:
            return files
        mime_prefix = FileType.get_mime_prefix(file_type)
        filtered = []
        if mime_prefix:
            filtered = [f for f in files if f.get('mime_type', '').startswith(mime_prefix)]
        return filtered


class DownloadFilesView(View):
    """View for downloading selected files."""

    def post(self, request: HttpRequest) -> HttpResponse:
        token = YandexDiskService.get_yandex_disk_token(request)
        if not token:
            return redirect(reverse('auth_url'))

        file_urls = request.POST.getlist(key='files')
        if not file_urls:
            return redirect(reverse('home'))

        try:
            zip_buffer = self._create_zip_archive(file_urls)
            return self._build_zip_response(zip_buffer)
        except requests.RequestException:
            return redirect(reverse('home'))

    @staticmethod
    def _create_zip_archive(file_urls: List[str]) -> io.BytesIO:
        """Creates a ZIP archive from the specified files."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zip_file:
            for file_url in file_urls:
                response = requests.get(file_url)
                response.raise_for_status()

                original_filename = DownloadFilesView._extract_filename(file_url)
                zip_file.writestr(original_filename, response.content)
        buffer.seek(0)
        return buffer

    @staticmethod
    def _extract_filename(file_url: str) -> str:
        """Extracts the file name from a URL."""
        parsed_url = urlparse(file_url)
        query_params = parse_qs(parsed_url.query)
        filename = query_params.get('filename', ['downloaded_file'])[0]
        return filename

    @staticmethod
    def _build_zip_response(zip_buffer: io.BytesIO) -> HttpResponse:
        """Builds an HTTP response with a ZIP archive."""
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename=downloaded_files.zip'
        return response
