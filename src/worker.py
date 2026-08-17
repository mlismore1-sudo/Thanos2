from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .companies_house_stream import CompaniesHouseStream
from .database import connection, fetch_one
from .enrichment import parse_company_number
from .screening import normalize_text, whole_token_matches, sic_matches

WORKER_NAME = "company_stream_worker"
_worker_lock = threading.Lock()
_worker_started = False


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_checkpoint() -> int | None:
    row = fetch_one(
        "select timepoint from stream_checkpoints "
        "where stream_name = 'companies'"
    )
    if row and row.get("timepoint") is not None:
        return int(row["timepoint"])
    return None


def set_status(status: str, error: str | None = None) -> None:
    timestamp = now()
    with connection() as conn:
        conn.execute(
            "insert into worker_status "
            "(worker_name, process_id, status, heartbeat_at, last_error, updated_at) "
            "values (%s, %s, %s, %s, %s, %s) "
            "on conflict (worker_name) do update set "
            "process_id = excluded.process_id, status = excluded.status, "
            "heartbeat_at = excluded.heartbeat_at, last_error = excluded.last_error, "
            "updated_at = excluded.updated_at",
            (WORKER_NAME, str(os.getpid()), status, timestamp, error, timestamp),
        )
        conn.commit()


def save_checkpoint(timepoint: int) -> None:
    timestamp = now()
    with connection() as conn:
        conn.execute(
            "insert into stream_checkpoints "
            "(stream_name, timepoint, connection_status, last_event_at, "
            "last_heartbeat_at, updated_at) "
            "values ('companies', %s, 'connected', %s, %s, %s) "
            "on conflict (stream_name) do update set "
            "timepoint = excluded.timepoint, connection_status = 'connected', "
            "last_event_at = excluded.last_event_at, "
            "last_heartbeat_at = excluded.last_heartbeat_at, "
            "updated_at = excluded.updated_at",
            (timepoint, timestamp, timestamp, timestamp),
        )
        conn.commit()


def extract_company(payload: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    data = payload.get("data") or {}
    resource = payload.get("resource") or {}
    company_number = (
        payload.get("resource_id")
        or data.get("company_number")
        or resource.get("company_number")
    )
    return company_number, data or resource


def _json(value: Any) -> str:
    return json.dumps(value, default=str)


def _date_value(data: dict[str, Any]) -> str | None:
    value = data.get("date_of_creation")
    if value is None:
        return None
    return str(value)[:10]


def process_event(payload: dict[str, Any], event_hash: str) -> None:
    event = payload.get("event") or {}
    company_number, data = extract_company(payload)
    if not company_number:
        return

    name = data.get("company_name") or company_number
    sic_codes = data.get("sic_codes") or []
    date_of_creation = _date_value(data)
    timestamp = now()

    with connection() as conn:
        inserted = conn.execute(
            "insert into raw_events "
            "(event_type, company_number, payload, received_at) "
            "values (%s, %s, %s, %s) returning id",
            (event.get("type"), company_number, _json(payload), timestamp),
        ).fetchone()

        if not inserted:
            return

        conn.execute(
            "insert into companies "
            "(company_number, company_name, date_of_creation, sic_codes, "
            "raw_data, first_seen_at, last_seen_at, last_screened_at) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s) "
            "on conflict (company_number) do update set "
            "company_name = excluded.company_name, "
            "date_of_creation = coalesce(excluded.date_of_creation, companies.date_of_creation), "
            "sic_codes = excluded.sic_codes, "
            "raw_data = excluded.raw_data, "
            "last_seen_at = excluded.last_seen_at, "
            "last_screened_at = excluded.last_screened_at",
            (
                company_number,
                name,
                date_of_creation,
                _json(sic_codes),
                _json(data),
                timestamp,
                timestamp,
                timestamp,
            ),
        )

        conn.execute(
            "insert into enrichment_jobs (company_number, enrichment_scope) "
            "values (%s, 'initial_rest') "
            "on conflict (company_number) where enrichment_scope = 'initial_rest' do nothing",
            (company_number,),
        )

        conn.commit()


def stream_loop() -> None:
    backoff = 5
    while True:
        try:
            set_status("connecting")
            CompaniesHouseStream().run_forever(
                process_event,
                get_checkpoint,
                save_checkpoint,
            )
            backoff = 5
        except Exception as exc:
            try:
                set_status("degraded", str(exc)[:1000])
            except Exception:
                pass
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)


def start_worker() -> bool:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return False
        set_status("starting")
        _worker_started = True
        thread = threading.Thread(
            target=stream_loop,
            name="thanos-company-stream",
            daemon=True,
        )
        thread.start()
        return True
