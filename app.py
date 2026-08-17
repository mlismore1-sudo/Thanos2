"""Thanos Streamlit application."""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.database import fetch_all

st.set_page_config(page_title="Thanos Leads", page_icon="🎯", layout="wide")


def display_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (dict, list)):
        return str(value)
    return str(value)


def show_leads() -> None:
    st.title("Thanos qualifying leads")
    st.caption("Companies marked as leads and incorporated today in Europe/London.")

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
        st.error("The application could not read the lead view from Supabase.")
        st.code(str(exc))
        return

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
    show_leads()


if __name__ == "__main__":
    main()
