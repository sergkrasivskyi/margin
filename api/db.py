from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from api.settings import ApiSettings


@contextmanager
def connect(settings: ApiSettings) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=5,
        options="-c default_transaction_read_only=on",
    )
    try:
        yield conn
    finally:
        conn.close()
