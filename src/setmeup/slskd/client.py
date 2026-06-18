from __future__ import annotations

import time
from typing import Optional

import requests


class SlskdError(Exception):
    pass


class SlskdClient:
    def __init__(self, base_url: str, api_key: Optional[str], session=None,
                 poll_interval: float = 1.0, request_timeout: float = 30.0):
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.poll_interval = poll_interval
        self.request_timeout = request_timeout

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def _get(self, path: str):
        resp = self.session.get(self.base + path, headers=self._headers(),
                                timeout=self.request_timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload):
        resp = self.session.post(self.base + path, json=payload,
                                 headers=self._headers(), timeout=self.request_timeout)
        resp.raise_for_status()
        return resp.json() if resp.status_code != 204 else None

    def search(self, text: str) -> str:
        data = self._post("/api/v0/searches", {"searchText": text})
        search_id = (data or {}).get("id")
        if not search_id:
            raise SlskdError(f"no search id in response: {data!r}")
        return str(search_id)

    def wait_for_responses(self, search_id: str, timeout: float) -> list[dict]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self._get(f"/api/v0/searches/{search_id}")
            if state.get("isComplete") or "completed" in str(state.get("state", "")).lower():
                break
            time.sleep(self.poll_interval)
        responses = self._get(f"/api/v0/searches/{search_id}/responses")
        return responses if isinstance(responses, list) else []

    def enqueue(self, username: str, files: list[dict]) -> None:
        self._post(f"/api/v0/transfers/downloads/{username}", files)

    def transfer_state(self, username: str, filename: str) -> str:
        data = self._get(f"/api/v0/transfers/downloads/{username}")
        for directory in data.get("directories", []):
            for file in directory.get("files", []):
                if file.get("filename") == filename:
                    return str(file.get("state", "Unknown"))
        return "NotFound"
