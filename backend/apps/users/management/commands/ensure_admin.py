"""
Create (or update) the admin-site superuser from environment variables.

Hosts without a shell (Render's free plan) cannot run `createsuperuser`, so this runs on
every start and does nothing unless ADMIN_USERNAME and ADMIN_PASSWORD are both set.

    ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL (optional)
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the admin superuser from ADMIN_USERNAME / ADMIN_PASSWORD."

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not username or not password:
            self.stdout.write("ensure_admin: ADMIN_USERNAME/ADMIN_PASSWORD not set, skipping.")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        email = os.environ.get("ADMIN_EMAIL", "").strip()
        if email and not user.email:
            user.email = email
        user.set_password(password)
        user.save()
        self.stdout.write(f"ensure_admin: {'created' if created else 'updated'} superuser {username!r}.")
