from __future__ import annotations

import queue
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import PureWindowsPath

from setmeup.slskd.selection import SelectionTarget, candidates_from_responses, rank
from setmeup.state import wants as wants_repo
from setmeup.state.wants import Want, WantStatus


@dataclass
class FetchEvent:
    want_id: int
    fields: dict


def _basename(filename: str) -> str:
    return PureWindowsPath(filename).name


def _is_complete(state: str) -> bool:
    return "succeeded" in state.lower()


def _is_terminal(state: str) -> bool:
    low = state.lower()
    return any(s in low for s in ("succeeded", "errored", "cancelled", "failed", "notfound"))


def _poll_transfer(client, username, filename, config) -> str:
    deadline = time.monotonic() + config.download_timeout_seconds
    while time.monotonic() < deadline:
        state = client.transfer_state(username, filename)
        if _is_terminal(state):
            return state
        time.sleep(1.0)
    return "Timeout"


def _worker(want: Want, client, config, emit) -> None:
    emit(FetchEvent(want.id, {"status": WantStatus.SEARCHING.value}))
    try:
        search_id = client.search(f"{want.artist} {want.title}")
        responses = client.wait_for_responses(search_id, config.search_timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        emit(FetchEvent(want.id, {"status": WantStatus.FAILED.value,
                                  "error": f"search error: {exc}",
                                  "attempts": want.attempts + 1}))
        return

    target = SelectionTarget(want.artist, want.title, want.version, want.duration_ms)
    ranked = rank(target, candidates_from_responses(responses), config)
    if not ranked:
        emit(FetchEvent(want.id, {"status": WantStatus.NO_MATCH.value,
                                  "error": "no candidate above thresholds"}))
        return

    for cand in ranked[: config.download_attempts]:
        emit(FetchEvent(want.id, {"status": WantStatus.DOWNLOADING.value,
                                  "slskd_username": cand.username,
                                  "slskd_filename": cand.filename}))
        try:
            client.enqueue(cand.username, [{"filename": cand.filename, "size": cand.size}])
            state = _poll_transfer(client, cand.username, cand.filename, config)
        except Exception:  # noqa: BLE001
            continue
        if _is_complete(state):
            emit(FetchEvent(want.id, {"status": WantStatus.DOWNLOADED.value,
                                      "downloaded_path": _basename(cand.filename)}))
            return

    emit(FetchEvent(want.id, {"status": WantStatus.FAILED.value,
                              "error": "all candidates failed",
                              "attempts": want.attempts + 1}))


def fetch(conn: sqlite3.Connection, config, client,
          statuses=("wanted",), limit: int = 0) -> dict:
    pending: list[Want] = []
    for status in statuses:
        pending.extend(wants_repo.get_wants_by_status(conn, status))
    if limit > 0:
        pending = pending[:limit]

    events: "queue.Queue[FetchEvent]" = queue.Queue()

    def emit(event: FetchEvent) -> None:
        events.put(event)

    def drain() -> None:
        while True:
            try:
                event = events.get_nowait()
            except queue.Empty:
                return
            wants_repo.update_want(conn, event.want_id, **event.fields)

    with ThreadPoolExecutor(max_workers=config.search_concurrency) as pool:
        futures = {pool.submit(_worker, want, client, config, emit) for want in pending}
        while futures:
            drain()
            futures = {f for f in futures if not f.done()}
            time.sleep(0.02)
    drain()  # final flush
    return wants_repo.count_wants_by_status(conn)
