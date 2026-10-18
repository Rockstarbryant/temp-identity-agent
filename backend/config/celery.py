import os

from celery import Celery
from celery.signals import task_postrun, task_prerun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("temp_identity_agent")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


@task_prerun.connect
@task_postrun.connect
def _fresh_db_connection(*args, **kwargs):
    """
    Start and end every task on a fresh DB connection. A worker process can sit idle for
    hours between jobs; the server has long since closed that connection, and the first
    query of the next job would fail with "SSL connection has been closed unexpectedly".
    """
    from django.db import connections

    connections.close_all()
