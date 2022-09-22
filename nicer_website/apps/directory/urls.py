from django.urls import path
from . import views


app_name = 'directory'
urlpatterns = [
    path('directory', views.directory, name='directory'),
]
