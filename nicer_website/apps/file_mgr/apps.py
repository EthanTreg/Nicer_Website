"""
Declare file_mgr app
"""
from django.apps import AppConfig


class DirectoryConfig(AppConfig):
    """
    Class representing the file_mgr application and its configuration
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nicer_website.apps.file_mgr'
