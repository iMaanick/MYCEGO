from django.urls import path
from .views import AuthUrlView, AuthTokenView, HomeView, DownloadFilesView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('auth/url/', AuthUrlView.as_view(), name='auth_url'),
    path('auth/token/', AuthTokenView.as_view(), name='auth_token'),
    path('download_files/', DownloadFilesView.as_view(), name='download_files'),

]
