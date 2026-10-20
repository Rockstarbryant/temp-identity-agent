from apps.accounts.models import TemporaryAccount


def ensure_vault_account(job):
    """
    A completed account-registration job must always have a vault entry, however the agent
    chose to finish it. Returns the account, or None when the job isn't one that should have one.
    """
    if job.state != "completed" or job.kind != "registration" or job.identity_id is None:
        return None
    account, _ = TemporaryAccount.objects.get_or_create(
        job=job, defaults={"identity": job.identity, "website": job.target_website})
    return account
