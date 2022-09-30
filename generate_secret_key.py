from django.core.management.utils import get_random_secret_key

print(f"SECRET_KEY = '{get_random_secret_key()}'")