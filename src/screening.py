from __future__ import annotations

import re
import unicodedata
from typing import Iterable


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def whole_token_matches(name: str, buzzwords: Iterable[str]) -> list[str]:
    normalized_name = normalize_text(name)
    tokens = set(normalized_name.split())
    matches = []
    for word in buzzwords:
        normalized_word = normalize_text(word)
        if normalized_word and normalized_word in tokens:
            matches.append(word)
    return matches


def sic_matches(sic_codes: Iterable[str], restricted_codes: set[str]) -> list[str]:
    return [str(code).strip() for code in sic_codes if str(code).strip() in restricted_codes]


def target_country(value: str | None, target_values: set[str]) -> str | None:
    normalized = normalize_text(value)
    for candidate in target_values:
        if normalized == normalize_text(candidate):
            return candidate
    return None


def restricted_qualified(has_target_director: bool, has_corporate_owner: bool) -> bool:
    return has_target_director or has_corporate_owner
