from __future__ import annotations

import os
from typing import Any

import requests

from .screening import TARGET_COUNTRIES, normalize_text


def parse_company_number(value: str) -> str:
    return str(value).strip().upper()


def _rest_key() -> str:
    value = os.getenv("COMPANIES_HOUSE_REST_API_KEY")
    if not value:
        raise RuntimeError("COMPANIES_HOUSE_REST_API_KEY is not configured")
    return value


def _base_url() -> str:
    return os.getenv(
        "REST_BASE_URL",
        "https://api.company-information.service.gov.uk",
    ).rstrip("/")


def get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(
        f"{_base_url()}{path}",
        params=params,
        auth=(_rest_key(), ""),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_company_profile(company_number: str) -> dict[str, Any]:
    return get_json(f"/company/{parse_company_number(company_number)}")


def get_officers(company_number: str) -> dict[str, Any]:
    return get_json(f"/company/{parse_company_number(company_number)}/officers")


def get_pscs(company_number: str) -> dict[str, Any]:
    return get_json(f"/company/{parse_company_number(company_number)}/persons-with-significant-control")


def _country_matches(value: Any) -> bool:
    candidate = normalize_text(value)
    return any(normalize_text(country) in candidate for country in TARGET_COUNTRIES)


def evaluate_restricted_company(
    company_number: str,
    profile: dict[str, Any],
    officers: dict[str, Any],
    pscs: dict[str, Any],
) -> dict[str, Any]:
    matching_directors: list[dict[str, Any]] = []
    for officer in officers.get("items") or []:
        officer_address = officer.get("address") or {}
        country = officer_address.get("country") or officer_address.get("locality")
        if officer.get("officer_role") in {"director", "corporate-director"} and _country_matches(country):
            matching_directors.append(
                {
                    "name": officer.get("name"),
                    "role": officer.get("officer_role"),
                    "appointed_on": officer.get("appointed_on"),
                    "country": country,
                }
            )

    matching_corporate_owners: list[dict[str, Any]] = []
    for psc in pscs.get("items") or []:
        identification = psc.get("identification") or {}
        address = psc.get("address") or {}
        country = (
            identification.get("country_registered")
            or address.get("country")
            or address.get("locality")
        )
        kind = normalize_text(psc.get("kind"))
        if "corporate" in kind and _country_matches(country):
            matching_corporate_owners.append(
                {
                    "name": psc.get("name"),
                    "kind": psc.get("kind"),
                    "country": country,
                    "natures_of_control": psc.get("natures_of_control") or [],
                }
            )

    qualified = bool(matching_directors or matching_corporate_owners)
    return {
        "company_number": company_number,
        "qualified": qualified,
        "matching_directors": matching_directors,
        "matching_corporate_owners": matching_corporate_owners,
        "evidence": {
            "profile": profile,
            "directors": matching_directors,
            "corporate_owners": matching_corporate_owners,
        },
    }


def enrich_and_evaluate(company_number: str) -> dict[str, Any]:
    profile = get_company_profile(company_number)
    officers = get_officers(company_number)
    pscs = get_pscs(company_number)
    return evaluate_restricted_company(company_number, profile, officers, pscs)
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
