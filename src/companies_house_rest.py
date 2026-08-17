from __future__ import annotations

import os
from typing import Any

import requests


class CompaniesHouseREST:
    def __init__(self) -> None:
        self.base_url = os.getenv("REST_BASE_URL", "https://api.company-information.service.gov.uk").rstrip("/")
        self.api_key = os.getenv("COMPANIES_HOUSE_REST_API_KEY")
        if not self.api_key:
            raise RuntimeError("COMPANIES_HOUSE_REST_API_KEY is not configured")
        self.session = requests.Session()
        self.session.auth = (self.api_key, "")

    def get(self, path: str) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}{path}", timeout=30)
        response.raise_for_status()
        return response.json()

    def company(self, number: str) -> dict[str, Any]:
        return self.get(f"/company/{number}")

    def officers(self, number: str) -> dict[str, Any]:
        return self.get(f"/company/{number}/officers")

    def pscs(self, number: str) -> dict[str, Any]:
        return self.get(f"/company/{number}/persons-with-significant-control")

    def corporate_psc(self, number: str) -> dict[str, Any]:
        return self.get(f"/company/{number}/persons-with-significant-control/corporate-entity")
