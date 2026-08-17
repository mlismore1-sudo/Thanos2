from __future__ import annotations

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Thanos Leads", layout="wide")
st.title("Thanos — Companies House Lead Screening")

try:
    from src.auth import login
    from src.config import BUZZWORDS, RESTRICTED_SIC_CODES, TARGET_COUNTRIES
    from src.database import fetch_all, fetch_one
except Exception as exc:
    st.error("The application could not load its Python modules.")
    st.exception(exc)
    st.stop()


def show_worker_status() -> None:
    st.subheader("Worker status")
    try:
        row = fetch_one("select * from worker_status where worker_name='company_stream_worker'")
    except Exception as exc:
        st.error("The database connection could not be tested.")
        st.exception(exc)
        return
    if not row:
        st.info("Worker has not reported status yet")
        return
    cols = st.columns(4)
    cols[0].metric("Status", row.get("status", "-"))
    cols[1].metric("Heartbeat", str(row.get("heartbeat_at") or "-"))
    cols[2].metric("Queue depth", row.get("queue_depth", 0))
    cols[3].metric("Events committed", row.get("events_committed", 0))
    if row.get("last_error"):
        st.warning(row["last_error"])


def show_leads() -> None:
    st.subheader("Leads")
    try:
        rows = fetch_all(
            "select company_number, company_name, sic_codes, enrichment_status, first_seen_at, enrichment_completed_at "
            "from companies order by first_seen_at desc limit 500"
        )
    except Exception as exc:
        st.error("The database connection could not be tested.")
        st.exception(exc)
        return
    if not rows:
        st.info("No companies received yet")
        return
    df = pd.DataFrame(rows)
    term = st.text_input("Filter company name")
    if term:
        df = df[df["company_name"].str.contains(term, case=False, na=False)]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "Export CSV",
        df.to_csv(index=False).encode("utf-8"),
        "thanos_leads.csv",
        "text/csv",
    )


def show_shortlist() -> None:
    st.subheader("Shortlist")
    try:
        rows = fetch_all(
            "select s.*, c.company_name "
            "from shortlist s join companies c using(company_number) "
            "order by s.updated_at desc"
        )
    except Exception as exc:
        st.error("The database connection could not be tested.")
        st.exception(exc)
        return
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No shortlisted companies")


def main() -> None:
    if not login():
        return

    st.caption(f"Signed in as {st.session_state.get('user')}")
    tabs = st.tabs(["Leads", "Worker", "Shortlist", "Rules"])

    with tabs[0]:
        show_leads()
    with tabs[1]:
        show_worker_status()
    with tabs[2]:
        show_shortlist()
    with tabs[3]:
        st.write("Buzzwords")
        st.code("\n".join(BUZZWORDS))
        st.write(f"Restricted SIC codes configured: {len(RESTRICTED_SIC_CODES)}")
        st.write(f"Target countries configured: {len(TARGET_COUNTRIES)}")


if __name__ == "__main__":
    main()
