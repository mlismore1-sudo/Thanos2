"""Thanos Streamlit dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from src.database import connection, fetch_all, fetch_one
from src.worker import start_worker

st.set_page_config(page_title="Thanos Leads", page_icon="🎯", layout="wide")

WORKER_NAME = "company_stream_worker"


def display_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (dict, list)):
        return str(value)
    return str(value)


def database_health() -> tuple[bool, str]:
    try:
        with connection() as conn:
            conn.execute("select 1").fetchone()
        return True, "Connected"
    except Exception as exc:
        return False, str(exc)


def worker_health() -> tuple[str, dict[str, Any] | None]:
    try:
        row = fetch_one(
            """
            select worker_name, status, heartbeat_at, last_event_at,
                   events_received, events_committed, last_error, updated_at
            from public.worker_status
            where worker_name = %s
            """,
            (WORKER_NAME,),
        )
    except Exception as exc:
        return f"Database error: {exc}", None

    if not row:
        return "Not started", None

    heartbeat = row.get("heartbeat_at")
    if isinstance(heartbeat, datetime):
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - heartbeat).total_seconds()
        if age > 300:
            return "Stale", row

    return str(row.get("status") or "Unknown"), row


def health_panel() -> None:
    st.subheader("System health")
    db_ok, db_message = database_health()
    current_worker_status, worker_row = worker_health()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Database", "Connected" if db_ok else "Not connected")
        if not db_ok:
            st.caption(db_message)
    with col2:
        st.metric("Worker", current_worker_status)
    with col3:
        st.metric(
            "Events committed",
            worker_row.get("events_committed", 0) if worker_row else 0,
        )

    if worker_row and worker_row.get("last_error"):
        st.warning(f"Worker error: {worker_row['last_error']}")


def worker_controls() -> None:
    st.subheader("Worker controls")
    st.caption(
        "The worker runs in a background thread inside this Streamlit process. "
        "It stops when the app process stops or restarts."
    )

    if st.button("Start worker", type="primary"):
        try:
            started = start_worker()
            if started:
                st.success("Worker start requested. Refresh health status in a few seconds.")
            else:
                st.info("Worker is already running in this process.")
        except Exception as exc:
            st.error("The worker could not be started.")
            st.code(str(exc))

    if st.button("Refresh health"):
        st.rerun()


def show_leads() -> None:
    try:
        rows = fetch_all(
            """
            select company_number, company_name, date_of_creation, sic_codes,
                   registered_office_address, company_status, enrichment_status,
                   lead_status, matched_buzzwords, matched_sic_codes,
                   incorporated_today, first_seen_at, last_seen_at
            from public.qualifying_leads
            order by first_seen_at desc
            """
        )
    except Exception as exc:
        st.error("The application could not read public.qualifying_leads.")
        st.code(str(exc))
        return

    st.subheader("Qualifying leads")
    st.caption("Companies marked as leads and incorporated today in Europe/London.")

    if not rows:
        st.info("No qualifying leads have been recorded yet.")
        return

    st.metric("Qualifying leads", len(rows))

    for row in rows:
        company_number = row.get("company_number", "")
        company_name = row.get("company_name", "Unnamed company")
        with st.expander(f"{company_name} ({company_number})"):
            left, right = st.columns(2)
            with left:
                st.write(f"**Company number:** {display_value(company_number)}")
                st.write(f"**Incorporated:** {display_value(row.get('date_of_creation'))}")
                st.write(f"**Status:** {display_value(row.get('company_status'))}")
                st.write(f"**Lead status:** {display_value(row.get('lead_status'))}")
                st.write(f"**Enrichment:** {display_value(row.get('enrichment_status'))}")
            with right:
                st.write(f"**SIC matches:** {display_value(row.get('matched_sic_codes'))}")
                st.write(f"**Buzzword matches:** {display_value(row.get('matched_buzzwords'))}")
                st.write(f"**Address:** {display_value(row.get('registered_office_address'))}")
                st.write(f"**First seen:** {display_value(row.get('first_seen_at'))}")


def main() -> None:
    st.title("Thanos dashboard")
    health_panel()
    worker_controls()
    show_leads()


if __name__ == "__main__":
    main()
        row = fetch_one(
            """
            select worker_name, status, heartbeat_at, last_event_at,
                   events_received, events_committed, last_error, updated_at
            from public.worker_status
            where worker_name = %s
            """,
            (WORKER_NAME,),
        )
    except Exception as exc:
        return f"Database error: {exc}", None

    if not row:
        return "Not started", None

    heartbeat = row.get("heartbeat_at")
    if isinstance(heartbeat, datetime):
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - heartbeat).total_seconds()
        if age > 300:
            return "Stale", row

    return str(row.get("status") or "Unknown"), row


def health_panel() -> None:
    st.subheader("System health")
    db_ok, db_message = database_health()
    current_worker_status, worker_row = worker_health()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Database", "Connected" if db_ok else "Not connected")
        if not db_ok:
            st.caption(db_message)
    with col2:
        st.metric("Worker", current_worker_status)
    with col3:
        st.metric(
            "Events committed",
            worker_row.get("events_committed", 0) if worker_row else 0,
        )

    if worker_row and worker_row.get("last_error"):
        st.warning(f"Worker error: {worker_row['last_error']}")


def worker_controls() -> None:
    st.subheader("Worker controls")
    st.caption(
        "The worker runs in a background thread inside this Streamlit process. "
        "It stops when the app process stops or restarts."
    )

    if st.button("Start worker", type="primary"):
        try:
            started = start_worker()
            if started:
                st.success("Worker start requested. Refresh health status in a few seconds.")
            else:
                st.info("Worker is already running in this process.")
        except Exception as exc:
            st.error("The worker could not be started.")
            st.code(str(exc))

    if st.button("Refresh health"):
        st.rerun()


def show_leads() -> None:
    try:
        rows = fetch_all(
            """
            select
                company_number,
                company_name,
                date_of_creation,
                sic_codes,
                registered_office_address,
                company_status,
                enrichment_status,
                lead_status,
                matched_buzzwords,
                matched_sic_codes,
                incorporated_today,
                first_seen_at,
                last_seen_at
            from public.qualifying_leads
            order by first_seen_at desc
            """
        )
    except Exception as exc:
        st.error("The application could not read public.qualifying_leads.")
        st.code(str(exc))
        return

    st.subheader("Qualifying leads")
    st.caption("Companies marked as leads and incorporated today in Europe/London.")

    if not rows:
        st.info("No qualifying leads have been recorded yet.")
        return

    st.metric("Qualifying leads", len(rows))

    for row in rows:
        company_number = row.get("company_number", "")
        company_name = row.get("company_name", "Unnamed company")
        with st.expander(f"{company_name} ({company_number})"):
            left, right = st.columns(2)
            with left:
                st.write(f"**Company number:** {display_value(company_number)}")
                st.write(f"**Incorporated:** {display_value(row.get('date_of_creation'))}")
                st.write(f"**Status:** {display_value(row.get('company_status'))}")
                st.write(f"**Lead status:** {display_value(row.get('lead_status'))}")
                st.write(f"**Enrichment:** {display_value(row.get('enrichment_status'))}")
            with right:
                st.write(f"**SIC matches:** {display_value(row.get('matched_sic_codes'))}")
                st.write(f"**Buzzword matches:** {display_value(row.get('matched_buzzwords'))}")
                st.write(f"**Address:** {display_value(row.get('registered_office_address'))}")
                st.write(f"**First seen:** {display_value(row.get('first_seen_at'))}")


def main() -> None:
    st.title("Thanos dashboard")
    health_panel()
    worker_controls()
    show_leads()


if __name__ == "__main__":
    main()
