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


def now():
    return datetime.now(timezone.utc)


def get_checkpoint() -> int | None:
    row = fetch_one(
        "select timepoint from stream_checkpoints "
        "where stream_name='companies'"
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
            "process_id=excluded.process_id, status=excluded.status, "
            "heartbeat_at=excluded.heartbeat_at, last_error=excluded.last_error, "
            "updated_at=excluded.updated_at",
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
            "timepoint=excluded.timepoint, connection_status='connected', "
            "last_event_at=excluded.last_event_at, "
            "last_heartbeat_at=excluded.last_heartbeat_at, "
            "updated_at=excluded.updated_at",
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
    timestamp = now()

    with connection() as conn:
        inserted = conn.execute(
            "insert into raw_events "
            "(stream_name, event_hash, resource_id, event_type, timepoint, "
            "published_at, payload, processing_status) "
            "values ('companies', %s, %s, %s, %s, %s, %s, 'stored') "
            "on conflict (event_hash) do nothing returning id",
            (
                event_hash,
                company_number,
                event.get("type"),
                event.get("timepoint"),
                event.get("published_at"),
                json.dumps(payload),
            ),
        ).fetchone()

        if not inserted:
            return

        conn.execute(
            "insert into companies "
            "(company_number, company_name, company_name_normalized, sic_codes, "
            "latest_stream_timepoint, last_seen_at) "
            "values (%s, %s, %s, %s, %s, %s) "
            "on conflict (company_number) do update set "
            "company_name=excluded.company_name, "
            "company_name_normalized=excluded.company_name_normalized, "
            "sic_codes=excluded.sic_codes, "
            "latest_stream_timepoint=excluded.latest_stream_timepoint, "
            "last_seen_at=excluded.last_seen_at, updated_at=now()",
            (
                company_number,
                name,
                normalize_text(name),
                json.dumps(sic_codes),
                event.get("timepoint"),
                timestamp,
            ),
        )

        conn.execute(
            "insert into enrichment_jobs (company_number) values (%s) "
            "on conflict (company_number, enrichment_scope) do nothing",
            (company_number,),
        )

        conn.execute(
            "update raw_events set processing_status='processed' "
            "where event_hash=%s",
            (event_hash,),
        )

        conn.execute(
            "update worker_status set last_event_at=%s, "
            "events_received=events_received + 1, "
            "events_committed=events_committed + 1, "
            "heartbeat_at=%s, updated_at=%s "
            "where worker_name=%s",
            (timestamp, timestamp, timestamp, WORKER_NAME),
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
        _worker_started = True
        set_status("starting")
        thread = threading.Thread(
            target=stream_loop,
            name="thanos-company-stream",
            daemon=True,
        )
        thread.start()
        return True
