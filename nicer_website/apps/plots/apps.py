"""
Declare plots app
"""
from django.apps import AppConfig


class PlotsConfig(AppConfig):
    """
    Class representing the plots application and its configuration
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nicer_website.apps.plots'
