from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def load_lines(filename: str) -> list[str]:
    path = CONFIG_DIR / filename
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def load_targets() -> set[str]:
    data = json.loads((CONFIG_DIR / "target_countries.json").read_text())
    return set(data.get("explicit", [])) | set(data.get("eu_member_states", []))


DATABASE_URL = env("DATABASE_URL")
STREAM_API_KEY = env("COMPANIES_HOUSE_STREAM_API_KEY")
REST_API_KEY = env("COMPANIES_HOUSE_REST_API_KEY")
STREAM_URL = env("STREAM_URL", "https://stream.companieshouse.gov.uk/companies")
REST_BASE_URL = env("REST_BASE_URL", "https://api.company-information.service.gov.uk")
STREAM_ENABLED = env("STREAM_ENABLED", "true").lower() == "true"
ENRICHMENT_ENABLED = env("ENRICHMENT_ENABLED", "true").lower() == "true"
BUZZWORDS = load_lines("buzzwords.txt")
RESTRICTED_SIC_CODES = set(load_lines("restricted_sic_codes.txt"))
TARGET_COUNTRIES = load_targets()
