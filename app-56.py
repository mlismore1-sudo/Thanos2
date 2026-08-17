from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from src.auth import login
from src.config import BUZZWORDS, RESTRICTED_SIC_CODES, TARGET_COUNTRIES
from src.database import fetch_all, fetch_one, execute
from src.worker import start_worker
from src.screening import whole_token_matches

st.set_page_config(page_title="Thanos Leads", layout="wide")


def show_worker_status():
    st.subheader("Worker status")
    row = fetch_one("select * from worker_status where worker_name='company_stream_worker'")
    if not row:
        st.info("Worker has not reported status yet")
        return
    st.metric("Status", row["status"])
    cols = st.columns(4)
    cols[0].metric("Heartbeat", str(row["heartbeat_at"] or "-"))
    cols[1].metric("Last event", str(row["last_event_at"] or "-"))
    cols[2].metric("Queue depth", row["queue_depth"])
    cols[3].metric("Events committed", row["events_committed"])
    if row["last_error"]:
        st.warning(row["last_error"])


def show_leads():
    st.subheader("Leads")
    rows = fetch_all("""
        select c.company_number, c.company_name, c.sic_codes, c.enrichment_status,
               c.first_seen_at, c.enrichment_completed_at,
               exists(select 1 from company_officers co join officers o using(officer_key)
                      where co.company_number=c.company_number
                      and (o.nationality = any(%s) or o.country_of_residence = any(%s)
                           or o.address_country = any(%s))) as target_director,
               exists(select 1 from company_pscs cp join psc_entities p using(psc_key)
                      where cp.company_number=c.company_number
                      and p.kind in ('corporate-entity','corporate_entity','legal-person')) as corporate_owner
        from companies c order by c.first_seen_at desc limit 500
    """, (list(TARGET_COUNTRIES), list(TARGET_COUNTRIES), list(TARGET_COUNTRIES)))
    if not rows:
        st.info("No companies received yet")
        return
    df = pd.DataFrame(rows)
    term = st.text_input("Filter company name")
    if term:
        df = df[df["company_name"].str.contains(term, case=False, na=False)]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Export CSV", df.to_csv(index=False).encode("utf-8"), "thanos_leads.csv", "text/csv")


def show_shortlist():
    st.subheader("Shortlist")
    rows = fetch_all("select s.*, c.company_name from shortlist s join companies c using(company_number) order by s.updated_at desc")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True) if rows else st.info("No shortlisted companies")


def main():
    if not login():
        return
    start_worker()
    st.title("Thanos — Companies House Lead Screening")
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
        st.write(f"Restricted SIC codes: {len(RESTRICTED_SIC_CODES)}")
        st.write(f"Target countries configured: {len(TARGET_COUNTRIES)}")


if __name__ == "__main__":
    main()
