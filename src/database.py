from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    with psycopg.connect(url, row_factory=dict_row) as conn:
        yield conn


def execute(sql: str, params: tuple | dict = ()) -> None:
    with connection() as conn:
        conn.execute(sql, params)
        conn.commit()


def fetch_all(sql: str, params: tuple | dict = ()) -> list[dict]:
    with connection() as conn:
        return list(conn.execute(sql, params).fetchall())


def fetch_one(sql: str, params: tuple | dict = ()) -> dict | None:
    with connection() as conn:
        return conn.execute(sql, params).fetchone()
