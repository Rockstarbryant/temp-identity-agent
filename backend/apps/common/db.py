"""Database connection helpers for long-running worker tasks."""
from django.db import connection


def ensure_db_connection() -> None:
    """
    Drop the DB connection if the server has closed it, so the next query
    reconnects instead of raising "SSL connection has been closed unexpectedly"
    / "the connection is closed".

    Agent jobs sit idle between queries for a long time (LLM calls, page loads,
    waiting for a human) and managed Postgres / poolers close idle connections.
    Does nothing inside a transaction, where the connection must not be swapped.
    """
    if connection.in_atomic_block or connection.connection is None:
        return
    if not connection.is_usable():
        connection.close()


def retry_db(fn, attempts: int = 4, delay: float = 2.0):
    """
    Run `fn` (a DB read/write), and if the database can't be reached for a moment
    (a dropped SSL connection, a DNS blip on the host) drop the dead connection,
    wait, and try again. Re-raises the last error if it never comes back.
    """
    import time

    from django.db import InterfaceError, OperationalError

    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except (OperationalError, InterfaceError):
            connection.close()
            if attempt == attempts:
                raise
            time.sleep(delay * attempt)
