"""
Generates a secret key for Django and saves it to .env file
"""
from django.core.management.utils import get_random_secret_key

with open('../.env', 'w', encoding='utf-8') as file:
    file.write(f"SECRET_KEY = '{get_random_secret_key()}'")
