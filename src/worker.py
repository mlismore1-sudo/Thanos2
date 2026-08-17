from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .database import connection, fetch_one

WORKER_NAME = "company_stream_worker"
_worker_lock = threading.Lock()
_worker_started = False


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_checkpoint() -> int | None:
    row = fetch_one(
        "select timepoint from public.stream_checkpoints "
        "where stream_name = 'companies'"
    )
    if row and row.get("timepoint") is not None:
        return int(row["timepoint"])
    return None


def set_status(status: str, error: str | None = None) -> None:
    timestamp = now()
    with connection() as conn:
        conn.execute(
            "insert into public.worker_status "
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
            "insert into public.stream_checkpoints "
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


def process_event(payload: dict[str, Any], event_hash: str) -> None:
    event = payload.get("event") or {}
    company_number, data = extract_company(payload)
    if not company_number:
        return

    name = data.get("company_name") or company_number
    sic_codes = data.get("sic_codes") or []
    date_of_creation = data.get("date_of_creation")
    timestamp = now()

    with connection() as conn:
        conn.execute(
            "insert into public.raw_events "
            "(event_type, company_number, payload, received_at) "
            "values (%s, %s, %s, %s)",
            (
                event.get("type"),
                company_number,
                json.dumps(payload, default=str),
                timestamp,
            ),
        )

        conn.execute(
            "insert into public.companies "
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
                json.dumps(sic_codes, default=str),
                json.dumps(data, default=str),
                timestamp,
                timestamp,
                timestamp,
            ),
        )

        conn.execute(
            "insert into public.enrichment_jobs "
            "(company_number, enrichment_scope) "
            "values (%s, 'initial_rest') "
            "on conflict (company_number, enrichment_scope) do nothing",
            (company_number,),
        )
        conn.commit()


def stream_loop() -> None:
    backoff = 5

    try:
        from .companies_house_stream import CompaniesHouseStream
    except Exception as exc:
        set_status("degraded", f"Stream import/configuration error: {exc}")
        return

    while True:
        try:
            set_status("connecting")
            stream = CompaniesHouseStream()
            stream.run_forever(
                process_event,
                get_checkpoint,
                save_checkpoint,
                set_status,
            )
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            try:
                set_status("degraded", error_text[:1000])
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
