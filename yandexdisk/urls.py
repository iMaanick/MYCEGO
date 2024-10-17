from django.urls import path
from .views import AuthTokenView, HomeView, DownloadFilesView, LoginView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('auth/', LoginView.as_view(), name='login'),
    path('auth/token/', AuthTokenView.as_view(), name='auth'),
    path('download_files/', DownloadFilesView.as_view(), name='download_files'),

]
