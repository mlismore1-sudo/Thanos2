from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Iterator

import requests


logger = logging.getLogger(__name__)


class CompaniesHouseStream:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.getenv(
            "STREAM_URL",
            "https://stream.companieshouse.gov.uk/companies",
        )
        self.api_key = os.getenv("COMPANIES_HOUSE_STREAM_API_KEY")
        if not self.api_key:
            raise RuntimeError("COMPANIES_HOUSE_STREAM_API_KEY is not configured")

    def events(self, timepoint: int | None = None) -> Iterator[tuple[dict[str, Any], str]]:
        params = {} if timepoint is None else {"timepoint": timepoint}
        headers = {"Accept": "application/json"}

        logger.info(
            "Connecting to Companies House stream url=%s timepoint=%s",
            self.url,
            timepoint,
        )

        with requests.get(
            self.url,
            params=params,
            headers=headers,
            auth=(self.api_key, ""),
            stream=True,
            timeout=(30, 300),
        ) as response:
            logger.info(
                "Companies House stream response status=%s url=%s",
                response.status_code,
                response.url,
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                payload = json.loads(line)
                digest = hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode("utf-8")
                ).hexdigest()
                yield payload, digest

    def run_forever(self, callback, checkpoint_loader, checkpoint_saver) -> None:
        backoff = 2

        while True:
            checkpoint = checkpoint_loader()
            try:
                for payload, digest in self.events(checkpoint):
                    callback(payload, digest)
                    event = payload.get("event") or {}
                    if event.get("timepoint") is not None:
                        checkpoint_saver(int(event["timepoint"]))
                    backoff = 2
            except requests.HTTPError as exc:
                response = exc.response
                status = response.status_code if response is not None else "unknown"
                body = response.text[:500] if response is not None else ""
                message = f"Companies House HTTP {status}: {body}"
                logger.exception(message)
                raise RuntimeError(message) from exc
            except requests.RequestException as exc:
                logger.exception("Companies House network error: %s", exc)
                raise RuntimeError(f"Companies House network error: {exc}") from exc
            except json.JSONDecodeError as exc:
                logger.exception("Invalid JSON received from Companies House: %s", exc)
                raise RuntimeError(f"Invalid JSON from Companies House: {exc}") from exc
            except Exception as exc:
                logger.exception("Companies House stream error: %s", exc)
                raise RuntimeError(f"Companies House stream error: {exc}") from exc
            finally:
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                    callback(payload, digest)
                    event = payload.get("event", {})
                    if event.get("timepoint") is not None:
                        checkpoint_saver(int(event["timepoint"]))
                    backoff = 2
            except Exception:
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
