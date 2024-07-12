"""
URLs for the file_mgr app to call functions in views
"""
from django.urls import path
from . import views


app_name = 'file_mgr'  # pylint: disable=invalid-name
urlpatterns = [
    path('dir/<path:path>', views.directory, name='directory'),
    path('file/<path:path>', views.file, name='file'),
    path('file_request', views.file_request, name='file_request'),
]
