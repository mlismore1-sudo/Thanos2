from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .companies_house_rest import CompaniesHouseREST
from .database import connection


def parse_company_number(payload: dict[str, Any]) -> str | None:
    return payload.get("resource_id") or payload.get("data", {}).get("company_number")


def enrich_company(company_number: str) -> None:
    api = CompaniesHouseREST()
    company = api.company(company_number)
    officers = api.officers(company_number)
    try:
        pscs = api.pscs(company_number)
    except Exception:
        pscs = {"items": []}

    now = datetime.now(timezone.utc)
    with connection() as conn:
        conn.execute(
            "update companies set company_name=coalesce(%s, company_name), sic_codes=%s, registered_office=%s, enrichment_status='complete', enrichment_completed_at=%s, updated_at=%s where company_number=%s",
            (company.get("company_name"), json.dumps(company.get("sic_codes", [])), json.dumps(company.get("registered_office_address", {})), now, now, company_number),
        )
        for item in officers.get("items", []):
            key = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
            address = item.get("address", {}) or {}
            conn.execute(
                "insert into officers(officer_key,name,nationality,country_of_residence,address_country,raw_data) values(%s,%s,%s,%s,%s,%s) on conflict(officer_key) do update set raw_data=excluded.raw_data, updated_at=now()",
                (key, item.get("name"), item.get("nationality"), item.get("country_of_residence"), address.get("country"), json.dumps(item)),
            )
            conn.execute(
                "insert into company_officers(company_number,officer_key,role,appointed_on,resigned_on,raw_data) values(%s,%s,%s,%s,%s,%s) on conflict(company_number,officer_key) do update set raw_data=excluded.raw_data",
                (company_number, key, item.get("officer_role"), item.get("appointed_on"), item.get("resigned_on"), json.dumps(item)),
            )
        for item in pscs.get("items", []):
            key = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
            kind = item.get("kind", "unknown")
            identification = item.get("identification", {}) or {}
            address = item.get("address", {}) or {}
            conn.execute(
                "insert into psc_entities(psc_key,kind,name,nationality,country_of_residence,country_registered,legal_form,raw_data) values(%s,%s,%s,%s,%s,%s,%s,%s) on conflict(psc_key) do update set raw_data=excluded.raw_data, updated_at=now()",
                (key, kind, item.get("name"), item.get("nationality"), item.get("country_of_residence"), identification.get("country_registered"), identification.get("legal_form"), json.dumps(item)),
            )
            conn.execute(
                "insert into company_pscs(company_number,psc_key,ceased_on,raw_data) values(%s,%s,%s,%s) on conflict(company_number,psc_key) do update set raw_data=excluded.raw_data",
                (company_number, key, item.get("ceased_on"), json.dumps(item)),
            )
        conn.execute("update enrichment_jobs set status='complete', completed_at=%s where company_number=%s and enrichment_scope='initial_rest'", (now, company_number))
        conn.commit()
