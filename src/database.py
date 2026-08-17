"""PostgreSQL access for Thanos."""

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


def get_connection() -> psycopg.Connection:
    """Open a connection using the Supabase PostgreSQL connection string."""
    return psycopg.connect(
        _database_url(),
        row_factory=dict_row,
        connect_timeout=15,
    )


def fetch_all(sql: str, params: Iterable[Any] | Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a read-only query and return dictionaries."""
    with get_connection() as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
        except psycopg.Error as exc:
            detail = getattr(exc, "diag", None)
            relation = getattr(detail, "table_name", None) if detail else None
            hint = getattr(detail, "message_detail", None) if detail else None
            raise RuntimeError(
                "Supabase query failed; "
                f"sqlstate={getattr(exc, 'sqlstate', None)}, "
                f"relation={relation}, detail={hint or exc}"
            ) from exc


def fetch_one(sql: str, params: Iterable[Any] | Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """Execute a read-only query and return one dictionary or None."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()
