from __future__ import annotations

import re
from typing import Iterable, Any


# Replace these values with the exact agreed configuration if different.
TARGET_SIC_CODES: set[str] = set()
RESTRICTED_SIC_CODES: set[str] = set()
BUZZWORDS: tuple[str, ...] = ()
TARGET_COUNTRIES: tuple[str, ...] = ()


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_sic(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def sic_matches(company_sic_codes: Iterable[Any], configured_codes: Iterable[Any]) -> list[str]:
    configured = {normalize_sic(code) for code in configured_codes if normalize_sic(code)}
    return sorted({normalize_sic(code) for code in company_sic_codes if normalize_sic(code) in configured})


def whole_token_matches(text: str, words: Iterable[str]) -> list[str]:
    normalized = normalize_text(text)
    matches: list[str] = []
    for word in words:
        candidate = normalize_text(word)
        if candidate and re.search(rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])", normalized):
            matches.append(candidate)
    return sorted(set(matches))


def screen_company(
    company_name: str,
    company_sic_codes: Iterable[Any],
    date_of_creation: str | None,
    uk_today: str,
) -> dict[str, Any]:
    matched_target_sics = sic_matches(company_sic_codes, TARGET_SIC_CODES)
    matched_restricted_sics = sic_matches(company_sic_codes, RESTRICTED_SIC_CODES)
    matched_buzzwords = whole_token_matches(company_name, BUZZWORDS)
    incorporated_today = bool(date_of_creation and str(date_of_creation)[:10] == uk_today)
    has_general_match = bool(matched_target_sics or matched_buzzwords)
    is_provisional_lead = incorporated_today and has_general_match
    needs_enrichment = bool(is_provisional_lead and matched_restricted_sics)

    if not incorporated_today:
        lead_status = "not_today"
    elif not has_general_match:
        lead_status = "not_matching"
    elif needs_enrichment:
        lead_status = "enrichment_pending"
    else:
        lead_status = "qualified"

    return {
        "incorporated_today": incorporated_today,
        "matched_sic_codes": sorted(set(matched_target_sics + matched_restricted_sics)),
        "matched_buzzwords": matched_buzzwords,
        "restricted_sic_codes": matched_restricted_sics,
        "is_provisional_lead": is_provisional_lead,
        "needs_enrichment": needs_enrichment,
        "is_lead": is_provisional_lead and not needs_enrichment,
        "lead_status": lead_status,
    }
