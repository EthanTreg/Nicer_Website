from django.urls import path
from . import views


app_name = 'file_mgr'
urlpatterns = [
    path('dir', views.index, name='index'),
    path('dir/<path:path>', views.directory, name='directory'),
    path('file/<path:path>', views.file, name='file'),
]
