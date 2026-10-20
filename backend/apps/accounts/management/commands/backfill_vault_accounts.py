from django.core.management.base import BaseCommand

from apps.accounts.service import ensure_vault_account
from apps.registration.models import RegistrationJob


class Command(BaseCommand):
    help = "Create missing vault entries for completed registration jobs that have an identity but no account."

    def handle(self, *args, **options):
        jobs = RegistrationJob.objects.filter(
            state="completed", kind="registration", identity__isnull=False, account__isnull=True
        ).select_related("identity", "target_website")
        created = 0
        for job in jobs:
            if ensure_vault_account(job):
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created} vault entries."))
