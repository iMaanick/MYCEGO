import io
import zipfile
from typing import List, Dict

from urllib.parse import urlparse, parse_qs

import requests
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpRequest
from django.urls import reverse
from django.views import View
from requests_oauthlib import OAuth2Session

from djangoMYCEGO import settings
from .forms import PublicLinkForm, FileType
from .services.YandexDiskService import YandexDiskService


class LoginView(View):
    """
    View for displaying the login button and initiating OAuth authorization.
    """
    template_name = 'disk/login.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name)

    def post(self, request: HttpRequest) -> HttpResponse:
        oauth = OAuth2Session(
            client_id=settings.YANDEX_DISK_CLIENT_ID,
            redirect_uri=settings.YANDEX_DISK_REDIRECT_URI
        )
        authorization_url, state = oauth.authorization_url(settings.YANDEX_DISK_AUTH_URL)

        request.session['oauth_state'] = state

        return redirect(authorization_url)


class AuthTokenView(View):
    """
    A view to handle OAuth authentication with Yandex Disk using requests-oauthlib.
    Initiates the OAuth flow and handles the callback to exchange code for token.
    """
    template_name = 'disk/auth_token.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        code = request.GET.get('code')

        if not code:
            return redirect('login')

        try:
            token = self._exchange_code_for_token(request, code)
            request.session['yandex_disk_token'] = token
            return render(request, self.template_name)
        except Exception as e:
            return render(request, self.template_name, {'error': f'Ошибка при получении токена: {str(e)}'})

    @staticmethod
    def _exchange_code_for_token(request: HttpRequest, code: str) -> str:
        """
        Exchanges an authorization code for an access token using requests-oauthlib.
        """
        oauth = OAuth2Session(
            client_id=settings.YANDEX_DISK_CLIENT_ID,
            redirect_uri=settings.YANDEX_DISK_REDIRECT_URI,
            state=request.session.get('oauth_state')
        )

        token = oauth.fetch_token(
            token_url=settings.YANDEX_DISK_TOKEN_URL,
            code=code,
            client_secret=settings.YANDEX_DISK_CLIENT_SECRET
        )
        return token.get('access_token')


class HomeView(View):
    """
    View for displaying files from a public link.
    """
    template_name = 'disk/home.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        token = YandexDiskService.get_yandex_disk_token(request)
        if not token:
            return redirect(reverse('login'))
        form = PublicLinkForm()
        return render(request, self.template_name, {'form': form, 'files': []})

    def post(self, request: HttpRequest) -> HttpResponse:
        token = YandexDiskService.get_yandex_disk_token(request)
        if not token:
            return redirect(reverse('login'))

        form = PublicLinkForm(request.POST)
        files = []

        if form.is_valid():
            public_key = form.cleaned_data['public_key']
            file_type = form.cleaned_data.get('file_type', 'all')

            yandex_service = YandexDiskService(
                token=token
            )
            resources = yandex_service.get_public_resources(public_key)

            if resources is not None:
                files = self._filter_files(resources, file_type)
            else:
                form.add_error(None, 'Ошибка получения данных с Яндекс.Диска')

        return render(request, self.template_name, {'form': form, 'files': files})

    @staticmethod
    def _filter_files(files: List[Dict], file_type: str) -> List[Dict]:
        """
        Filters files by type.
        """
        if file_type == FileType.ALL:
            return files
        mime_prefix = FileType.get_mime_prefix(file_type)
        filtered = []
        if mime_prefix:
            filtered = [f for f in files if f.get('mime_type', '').startswith(mime_prefix)]
        return filtered


class DownloadFilesView(View):
    """
    View for downloading selected files.
    """

    def post(self, request: HttpRequest) -> HttpResponse:
        token = YandexDiskService.get_yandex_disk_token(request)
        if not token:
            return redirect(reverse('login'))

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
        """
        Creates a ZIP archive from the specified files.
        """
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
        """
        Extracts the file name from a URL.
        """
        parsed_url = urlparse(file_url)
        query_params = parse_qs(parsed_url.query)
        filename = query_params.get('filename', ['downloaded_file'])[0]
        return filename

    @staticmethod
    def _build_zip_response(zip_buffer: io.BytesIO) -> HttpResponse:
        """
        Builds an HTTP response with a ZIP archive.
        """
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename=downloaded_files.zip'
        return response
