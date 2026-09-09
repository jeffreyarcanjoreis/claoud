"""Unit tests for :func:`kairos.auth.supabase.signup` response parsing.

Regression coverage for the two shapes GoTrue's ``/auth/v1/signup`` returns:

- **autoconfirm on** → a session: the created user is nested under ``user``
  alongside an ``access_token``;
- **"Confirm email" on** → no session: the created user's fields come at the
  TOP LEVEL of the response, with no ``user`` wrapper and no ``access_token``
  (the case that broke a live activation and returned "sem user.id").

Plus the e-mail-enumeration case (already-registered e-mail with confirm-email
on → obfuscated user with an empty ``identities`` list).

The network call is mocked; no real Supabase request is made.
"""

import json

import pytest

from kairos.auth import supabase


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


@pytest.fixture
def _configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kairos.auth.supabase.config.supabase_url", lambda: "https://x.supabase.co"
    )
    monkeypatch.setattr(
        "kairos.auth.supabase.config.supabase_anon_key", lambda: "anon-key"
    )


def _mock_response(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    monkeypatch.setattr(
        "kairos.auth.supabase.urllib.request.urlopen",
        lambda request, timeout=None: _FakeResp(body),
    )


def test_signup_parses_top_level_user_when_confirm_email_on(
    _configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    # "Confirm email" on: user fields at the top level, no session.
    _mock_response(
        monkeypatch,
        {
            "id": "uid-top",
            "email": "aluno@x.com",
            "identities": [{"id": "1"}],
            "confirmation_sent_at": "2026-01-01T00:00:00Z",
        },
    )

    res = supabase.signup("aluno@x.com", "senha-forte-123")

    assert res["user_id"] == "uid-top"
    assert res["email"] == "aluno@x.com"
    assert res["access_token"] == ""


def test_signup_parses_nested_user_with_session(
    _configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Autoconfirm on: session returned, user nested under "user".
    _mock_response(
        monkeypatch,
        {
            "access_token": "tok-abc",
            "user": {"id": "uid-nested", "email": "aluno@x.com", "identities": [{}]},
        },
    )

    res = supabase.signup("aluno@x.com", "senha-forte-123")

    assert res["user_id"] == "uid-nested"
    assert res["access_token"] == "tok-abc"


def test_signup_empty_identities_means_email_already_registered(
    _configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Already-registered e-mail with confirm-email on: obfuscated user with an
    # empty identities list.
    _mock_response(
        monkeypatch,
        {"id": "0000", "email": "aluno@x.com", "identities": []},
    )

    with pytest.raises(supabase.AuthEmailJaRegistrado):
        supabase.signup("aluno@x.com", "senha-forte-123")
