from django.urls import path
from . import views


app_name = 'file_mgr'
urlpatterns = [
    path('dir/<path:path>', views.directory, name='directory'),
    path('file/<path:path>', views.file, name='file'),
    path('file_request', views.file_request, name='file_request'),
]
