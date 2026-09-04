"""Example tests — cross-account chat 403/404 (Task 2.14).

Feature: account-scoped-chat-and-isolation.
Validates: Requirements R5.4, R5.5, R6.3, R6.4, R6.5, R8.2.

Cross-account get/refine/delete on a session owned by another account -> 403;
a session that does not exist -> 404; never a 200-with-empty substitute. Also
asserts the new chat endpoints 401 without a valid X-Account-Id header.
"""

import fakes

A = {"X-Account-Id": "acct-aaaa"}
B = {"X-Account-Id": "acct-bbbb"}


def _create_chat(client, headers):
    resp = client.post("/api/chats", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["sessionId"]


def test_missing_header_401_on_chat_endpoints(client):
    assert client.get("/api/chats", headers={}).status_code == 401
    assert client.post("/api/chats", json={}, headers={}).status_code == 401
    assert client.get("/api/chats/session_x", headers={}).status_code == 401
    assert client.delete("/api/chats/session_x", headers={}).status_code == 401


def test_malformed_header_401_on_chat_endpoints(client):
    bad = {"X-Account-Id": "not-an-account"}
    assert client.get("/api/chats", headers=bad).status_code == 401
    assert client.post("/api/chats", json={}, headers=bad).status_code == 401


def test_cross_account_get_is_403(client):
    sid = _create_chat(client, A)
    resp = client.get(f"/api/chats/{sid}", headers=B)
    assert resp.status_code == 403
    # Not a 200-with-empty substitute.
    assert resp.status_code != 200


def test_cross_account_delete_is_403(client):
    sid = _create_chat(client, A)
    resp = client.delete(f"/api/chats/{sid}", headers=B)
    assert resp.status_code == 403
    # A's conversation still exists and is retrievable by A.
    assert client.get(f"/api/chats/{sid}", headers=A).status_code == 200


def test_cross_account_refine_is_403_and_persists_nothing(client):
    sid = _create_chat(client, A)
    client.set_search_results(fakes.make_result_rows(["img1"]))
    resp = client.post(
        "/api/refine",
        json={"message": "handwritten", "sessionId": sid, "activeClues": []},
        headers=B,
    )
    assert resp.status_code == 403
    # A opens its conversation: no refinement message leaked in.
    detail = client.get(f"/api/chats/{sid}", headers=A).json()
    assert all("handwritten" != m["content"] for m in detail["messages"])


def test_missing_session_get_is_404(client):
    resp = client.get("/api/chats/session_does_not_exist", headers=A)
    assert resp.status_code == 404


def test_missing_session_refine_is_404(client):
    resp = client.post(
        "/api/refine",
        json={"message": "x", "sessionId": "session_does_not_exist", "activeClues": []},
        headers=A,
    )
    assert resp.status_code == 404


def test_missing_session_delete_is_404(client):
    resp = client.delete("/api/chats/session_does_not_exist", headers=A)
    assert resp.status_code == 404


def test_search_persists_and_reloads(client):
    """End-to-end: search creates a conversation, persists the turn + refs, and
    the reloaded conversation shows the query and exactly the returned refs."""
    client.set_search_results(fakes.make_result_rows(["imgA", "imgB"]))
    resp = client.post("/api/search", json={"query": "find my CN notes"}, headers=A)
    assert resp.status_code == 200
    body = resp.json()
    sid = body["sessionId"]
    # TurnResponse shape unchanged: results present and payload untouched.
    assert len(body["results"]) == 2

    detail = client.get(f"/api/chats/{sid}", headers=A).json()
    user_msgs = [m for m in detail["messages"] if m["role"] == "user"]
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"] == "find my CN notes"
    assert len(user_msgs[0]["results"]) == 2
    # Refs carry no path/binary keys.
    for ref in user_msgs[0]["results"]:
        for k in (ref["displayMetadata"] or {}).keys():
            assert "path" not in str(k).lower()
