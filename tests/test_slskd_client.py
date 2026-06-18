import pytest

from setmeup.slskd.client import SlskdClient, SlskdError


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self):
        self.calls = []
        self.get_queue = []
        self.post_return = FakeResponse({"id": "search-1"})

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url))
        return self.get_queue.pop(0)

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json))
        return self.post_return


def test_search_returns_id():
    sess = FakeSession()
    client = SlskdClient("http://x", "key", session=sess)
    assert client.search("daft punk around the world") == "search-1"
    method, url, body = sess.calls[0]
    assert method == "POST" and url.endswith("/api/v0/searches")
    assert body == {"searchText": "daft punk around the world"}


def test_wait_for_responses_polls_until_complete():
    sess = FakeSession()
    sess.get_queue = [
        FakeResponse({"isComplete": False}),
        FakeResponse({"isComplete": True}),
        FakeResponse([{"username": "bob", "files": []}]),  # /responses
    ]
    client = SlskdClient("http://x", "key", session=sess, poll_interval=0)
    responses = client.wait_for_responses("search-1", timeout=5)
    assert responses == [{"username": "bob", "files": []}]


def test_transfer_state_finds_file():
    sess = FakeSession()
    sess.get_queue = [
        FakeResponse({"directories": [
            {"files": [
                {"filename": "music\\a.flac", "state": "Completed, Succeeded"},
            ]},
        ]}),
    ]
    client = SlskdClient("http://x", "key", session=sess)
    assert client.transfer_state("bob", "music\\a.flac") == "Completed, Succeeded"


def test_search_raises_on_missing_id():
    sess = FakeSession()
    sess.post_return = FakeResponse({})  # response has no "id"
    client = SlskdClient("http://x", "key", session=sess)
    with pytest.raises(SlskdError):
        client.search("anything")


def test_transfer_state_returns_not_found_when_absent():
    sess = FakeSession()
    sess.get_queue = [FakeResponse({"directories": []})]
    client = SlskdClient("http://x", "key", session=sess)
    assert client.transfer_state("bob", "missing.flac") == "NotFound"
