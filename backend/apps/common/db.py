"""Database connection helpers for long-running worker tasks."""
from django.db import connection


def ensure_db_connection() -> None:
    if connection.in_atomic_block or connection.connection is None:
        return
    if not connection.is_usable():
        connection.close()