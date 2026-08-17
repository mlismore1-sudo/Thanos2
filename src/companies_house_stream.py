from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Iterator

import requests


class CompaniesHouseStream:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.getenv("STREAM_URL", "https://stream.companieshouse.gov.uk/companies")
        self.api_key = os.getenv("COMPANIES_HOUSE_STREAM_API_KEY")
        if not self.api_key:
            raise RuntimeError("COMPANIES_HOUSE_STREAM_API_KEY is not configured")

    def events(self, timepoint: int | None = None) -> Iterator[tuple[dict, str]]:
        params = {} if timepoint is None else {"timepoint": timepoint}
        headers = {"Accept": "application/json"}
        with requests.get(self.url, params=params, headers=headers, auth=(self.api_key, ""), stream=True, timeout=(30, 300)) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                payload = json.loads(line)
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                yield payload, digest

    def run_forever(self, callback, checkpoint_loader, checkpoint_saver) -> None:
        backoff = 2
        while True:
            checkpoint = checkpoint_loader()
            try:
                for payload, digest in self.events(checkpoint):
                    callback(payload, digest)
                    event = payload.get("event", {})
                    if event.get("timepoint") is not None:
                        checkpoint_saver(int(event["timepoint"]))
                    backoff = 2
            except Exception:
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
