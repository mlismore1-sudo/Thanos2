"""PostgreSQL helpers used by the Thanos app and worker."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not configured")
    return value


def connection() -> psycopg.Connection:
    return psycopg.connect(
        _database_url(),
        row_factory=dict_row,
        connect_timeout=15,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )


def get_connection() -> psycopg.Connection:
    return connection()


def fetch_all(
    sql: str,
    params: Iterable[Any] | Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def fetch_one(
    sql: str,
    params: Iterable[Any] | Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
