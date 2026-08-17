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
from .enrichment import enrich_company, parse_company_number
from .screening import normalize_text, whole_token_matches, sic_matches


WORKER_NAME = "company_stream_worker"


def now():
    return datetime.now(timezone.utc)


def checkpoint() -> int | None:
    row = fetch_one("select timepoint from stream_checkpoints where stream_name='companies'")
    return row["timepoint"] if row and row["timepoint"] is not None else None


def save_checkpoint(value: int) -> None:
    with connection() as conn:
        conn.execute(
            "insert into stream_checkpoints(stream_name,timepoint,connection_status,last_heartbeat_at,updated_at) values('companies',%s,'connected',%s,%s) on conflict(stream_name) do update set timepoint=excluded.timepoint, connection_status='connected', last_heartbeat_at=excluded.last_heartbeat_at, updated_at=excluded.updated_at",
            (value, now(), now()),
        )
        conn.commit()


def worker_heartbeat(status: str = "running", error: str | None = None) -> None:
    with connection() as conn:
        conn.execute(
            "insert into worker_status(worker_name,process_id,status,heartbeat_at,last_error,updated_at) values(%s,%s,%s,%s,%s,%s) on conflict(worker_name) do update set status=excluded.status, heartbeat_at=excluded.heartbeat_at, last_error=excluded.last_error, updated_at=excluded.updated_at",
            (WORKER_NAME, str(os.getpid()), status, now(), error, now()),
        )
        conn.commit()


def process_event(payload: dict[str, Any], event_hash: str) -> None:
    event = payload.get("event", {}) or {}
    company_number = parse_company_number(payload)
    data = payload.get("data", {}) or {}
    if not company_number:
        return
    with connection() as conn:
        inserted = conn.execute(
            "insert into raw_events(stream_name,event_hash,resource_id,event_type,timepoint,published_at,payload) values('companies',%s,%s,%s,%s,%s,%s) on conflict(event_hash) do nothing returning id",
            (event_hash, company_number, event.get("type"), event.get("timepoint"), event.get("published_at"), json.dumps(payload)),
        ).fetchone()
        if not inserted:
            return
        name = data.get("company_name") or payload.get("company_name") or company_number
        sic_codes = data.get("sic_codes") or payload.get("sic_codes") or []
        conn.execute(
            "insert into companies(company_number,company_name,company_name_normalized,sic_codes,latest_stream_timepoint,last_seen_at) values(%s,%s,%s,%s,%s,%s) on conflict(company_number) do update set company_name=excluded.company_name, company_name_normalized=excluded.company_name_normalized, sic_codes=excluded.sic_codes, latest_stream_timepoint=excluded.latest_stream_timepoint, last_seen_at=excluded.last_seen_at, updated_at=now()",
            (company_number, name, normalize_text(name), json.dumps(sic_codes), event.get("timepoint"), now()),
        )
        conn.execute("insert into enrichment_jobs(company_number) values(%s) on conflict(company_number,enrichment_scope) do nothing", (company_number,))
        conn.commit()


def enrichment_loop() -> None:
    while True:
        try:
            row = fetch_one("select id, company_number from enrichment_jobs where status='pending' order by created_at limit 1")
            if not row:
                time.sleep(2)
                continue
            with connection() as conn:
                conn.execute("update enrichment_jobs set status='in_progress', attempts=attempts+1, started_at=now() where id=%s", (row["id"],))
                conn.execute("update companies set enrichment_status='in_progress' where company_number=%s", (row["company_number"],))
                conn.commit()
            try:
                enrich_company(row["company_number"])
            except Exception as exc:
                with connection() as conn:
                    conn.execute("update enrichment_jobs set status='pending', last_error=%s where id=%s", (str(exc)[:1000], row["id"]))
                    conn.execute("update companies set enrichment_status='retry_pending' where company_number=%s", (row["company_number"],))
                    conn.commit()
                time.sleep(5)
        except Exception as exc:
            worker_heartbeat("degraded", str(exc))
            time.sleep(10)


def start_worker() -> None:
    if os.getenv("STREAM_ENABLED", "true").lower() != "true":
        return
    if getattr(start_worker, "started", False):
        return
    start_worker.started = True
    threading.Thread(target=enrichment_loop, name="thanos-enrichment", daemon=True).start()

    def stream_loop():
        while True:
            try:
                worker_heartbeat("running")
                CompaniesHouseStream().run_forever(process_event, checkpoint, save_checkpoint)
            except Exception as exc:
                worker_heartbeat("degraded", str(exc))
                time.sleep(10)

    threading.Thread(target=stream_loop, name="thanos-stream", daemon=True).start()
