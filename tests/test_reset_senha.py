"""Tests for the "forgot my password" self-service flow (Supabase Auth).

Covers the functional specification:

- Gate: ``/esqueci-senha`` and ``/redefinir-senha`` are public paths (see
  ``kairos.auth.middleware._is_public``) — a visitor with no session can
  reach both without being bounced to ``/login``;
- ``/login`` shows a link to ``/esqueci-senha`` and, when redirected back
  with ``?redefinida=1``, a "password redefined" confirmation;
- ``GET/POST /esqueci-senha``: always answers with the same generic
  "if there is an account with that e-mail" message, whether or not the
  e-mail exists and whether or not ``supabase.recover`` succeeds
  (anti-enumeration; the request never reveals which case happened);
- ``GET/POST /redefinir-senha``: an empty ``access_token`` is rejected
  (400) before any Supabase call; a short/mismatched password is rejected
  (200, re-rendered with an error) without calling
  ``supabase.atualizar_senha``; ``AuthTokenInvalido`` maps to the same 400
  "invalid/expired link" response as a missing token; any other
  ``AuthError`` re-renders the form with a generic failure message;
  success redirects (303) to ``/login?redefinida=1``.

Every route test mocks ``kairos.auth.routes.supabase.recover`` /
``kairos.auth.routes.supabase.atualizar_senha`` — the exact attributes the
routes call (``kairos/auth/routes.py`` does ``from kairos.auth import ...
supabase`` and then ``supabase.recover(...)``/``supabase.atualizar_senha(...)``)
— so no test in this file ever reaches the network. The last section covers
the integration layer itself (:mod:`kairos.auth.supabase`) with
``urllib.request.urlopen`` mocked, the same pattern as
``tests/test_supabase_signup.py``.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a
temp dir and the cached engine is disposed on setup/teardown; the suite-wide
``_no_remote_database_url`` fixture (tests/conftest.py) already strips
``KAIROS_DATABASE_URL`` for every test.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.auth import supabase
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# Gate: /esqueci-senha and /redefinir-senha are public
# ---------------------------------------------------------------------------


@pytest.mark.real_auth
def test_get_esqueci_senha_is_public_without_login(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/esqueci-senha", follow_redirects=False)

    assert response.status_code == 200


@pytest.mark.real_auth
def test_get_redefinir_senha_is_public_without_login(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/redefinir-senha", follow_redirects=False)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /login: link to "esqueci minha senha" and "redefinida" confirmation
# ---------------------------------------------------------------------------


def test_login_shows_forgot_password_link(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/login")

    assert response.status_code == 200
    assert "Esqueci minha senha" in response.text
    assert 'href="/esqueci-senha"' in response.text


def test_login_with_redefinida_shows_confirmation(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/login?redefinida=1")

    assert response.status_code == 200
    assert "Senha redefinida" in response.text


# ---------------------------------------------------------------------------
# GET /esqueci-senha
# ---------------------------------------------------------------------------


def test_get_esqueci_senha_shows_form(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/esqueci-senha")

    assert response.status_code == 200
    assert 'name="email"' in response.text


# ---------------------------------------------------------------------------
# POST /esqueci-senha
# ---------------------------------------------------------------------------


def test_post_esqueci_senha_calls_recover_with_email_and_redirect_to(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def _fake_recover(email: str, redirect_to: str) -> None:
        calls.append((email, redirect_to))

    monkeypatch.setattr("kairos.auth.routes.supabase.recover", _fake_recover)

    with TestClient(app) as client:
        response = client.post(
            "/esqueci-senha", data={"email": "aluno@example.com"}
        )

    assert response.status_code == 200
    assert "Se houver uma conta" in response.text
    assert len(calls) == 1
    email, redirect_to = calls[0]
    assert email == "aluno@example.com"
    assert redirect_to.endswith("/redefinir-senha")


def test_post_esqueci_senha_when_recover_raises_auth_error_shows_generic_message(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_recover(email: str, redirect_to: str) -> None:
        raise supabase.AuthError("boom")

    monkeypatch.setattr("kairos.auth.routes.supabase.recover", _fake_recover)

    with TestClient(app) as client:
        response = client.post(
            "/esqueci-senha", data={"email": "aluno@example.com"}
        )

    assert response.status_code == 200
    # Never leaks the internal exception detail.
    assert "boom" not in response.text


def test_post_esqueci_senha_response_does_not_reveal_whether_email_exists(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Supabase's own `/auth/v1/recover` never distinguishes a registered
    # e-mail from an unregistered one (it always answers 200 and
    # `supabase.recover` never raises for that case): the same generic
    # message must come back for any e-mail submitted, and it must never
    # echo the e-mail itself back into the page.
    def _fake_recover(email: str, redirect_to: str) -> None:
        return None

    monkeypatch.setattr("kairos.auth.routes.supabase.recover", _fake_recover)

    with TestClient(app) as client:
        response_a = client.post(
            "/esqueci-senha", data={"email": "existe@example.com"}
        )
        response_b = client.post(
            "/esqueci-senha", data={"email": "nao-existe@example.com"}
        )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert "existe@example.com" not in response_a.text
    assert "nao-existe@example.com" not in response_b.text
    assert "Se houver uma conta" in response_a.text
    assert "Se houver uma conta" in response_b.text
    assert response_a.text == response_b.text


# ---------------------------------------------------------------------------
# GET /redefinir-senha
# ---------------------------------------------------------------------------


def test_get_redefinir_senha_shows_form(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/redefinir-senha")

    assert response.status_code == 200
    assert 'name="access_token"' in response.text
    assert 'name="senha"' in response.text
    assert 'name="confirmar"' in response.text


# ---------------------------------------------------------------------------
# POST /redefinir-senha: validation before calling Supabase
# ---------------------------------------------------------------------------


def test_post_redefinir_senha_with_empty_access_token_returns_400(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = {"called": False}

    def _fake_atualizar_senha(access_token: str, senha: str) -> None:
        flag["called"] = True

    monkeypatch.setattr(
        "kairos.auth.routes.supabase.atualizar_senha", _fake_atualizar_senha
    )

    with TestClient(app) as client:
        response = client.post(
            "/redefinir-senha",
            data={"access_token": "", "senha": "12345678", "confirmar": "12345678"},
        )

    assert response.status_code == 400
    assert "Link inválido ou expirado" in response.text
    assert flag["called"] is False


def test_post_redefinir_senha_with_short_password_does_not_call_atualizar_senha(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = {"called": False}

    def _fake_atualizar_senha(access_token: str, senha: str) -> None:
        flag["called"] = True

    monkeypatch.setattr(
        "kairos.auth.routes.supabase.atualizar_senha", _fake_atualizar_senha
    )

    with TestClient(app) as client:
        response = client.post(
            "/redefinir-senha",
            data={"access_token": "tok-123", "senha": "curta", "confirmar": "curta"},
        )

    assert response.status_code == 200
    assert flag["called"] is False


def test_post_redefinir_senha_with_mismatched_passwords_does_not_call_atualizar_senha(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = {"called": False}

    def _fake_atualizar_senha(access_token: str, senha: str) -> None:
        flag["called"] = True

    monkeypatch.setattr(
        "kairos.auth.routes.supabase.atualizar_senha", _fake_atualizar_senha
    )

    with TestClient(app) as client:
        response = client.post(
            "/redefinir-senha",
            data={
                "access_token": "tok-123",
                "senha": "12345678",
                "confirmar": "87654321",
            },
        )

    assert response.status_code == 200
    assert flag["called"] is False


# ---------------------------------------------------------------------------
# POST /redefinir-senha: success and Supabase failures
# ---------------------------------------------------------------------------


def test_post_redefinir_senha_success_redirects_to_login_redefinida(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def _fake_atualizar_senha(access_token: str, senha: str) -> None:
        calls.append((access_token, senha))

    monkeypatch.setattr(
        "kairos.auth.routes.supabase.atualizar_senha", _fake_atualizar_senha
    )

    with TestClient(app) as client:
        response = client.post(
            "/redefinir-senha",
            data={
                "access_token": "tok-123",
                "senha": "12345678",
                "confirmar": "12345678",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?redefinida=1"
    assert calls == [("tok-123", "12345678")]


def test_post_redefinir_senha_with_invalid_token_returns_400(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_atualizar_senha(access_token: str, senha: str) -> None:
        raise supabase.AuthTokenInvalido("boom")

    monkeypatch.setattr(
        "kairos.auth.routes.supabase.atualizar_senha", _fake_atualizar_senha
    )

    with TestClient(app) as client:
        response = client.post(
            "/redefinir-senha",
            data={
                "access_token": "tok-expirado",
                "senha": "12345678",
                "confirmar": "12345678",
            },
        )

    assert response.status_code == 400
    assert "Link inválido ou expirado" in response.text


def test_post_redefinir_senha_when_atualizar_senha_raises_auth_error(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_atualizar_senha(access_token: str, senha: str) -> None:
        raise supabase.AuthError("boom")

    monkeypatch.setattr(
        "kairos.auth.routes.supabase.atualizar_senha", _fake_atualizar_senha
    )

    with TestClient(app) as client:
        response = client.post(
            "/redefinir-senha",
            data={
                "access_token": "tok-123",
                "senha": "12345678",
                "confirmar": "12345678",
            },
        )

    assert response.status_code == 200
    assert "boom" not in response.text


# ---------------------------------------------------------------------------
# kairos.auth.supabase: recover() / atualizar_senha() (unit, urlopen mocked)
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, body: bytes = b"") -> None:
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


def test_recover_returns_none_on_success_and_hits_recover_endpoint(
    _configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def _fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        return _FakeResp()

    monkeypatch.setattr(
        "kairos.auth.supabase.urllib.request.urlopen", _fake_urlopen
    )

    result = supabase.recover(
        "aluno@example.com", "http://testserver/redefinir-senha"
    )

    assert result is None
    assert "/auth/v1/recover" in captured["url"]
    assert "redefinir-senha" in captured["url"]


def test_atualizar_senha_returns_none_on_success(
    _configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "kairos.auth.supabase.urllib.request.urlopen",
        lambda request, timeout=None: _FakeResp(),
    )

    result = supabase.atualizar_senha("tok-válido", "nova-senha-123")

    assert result is None


def test_atualizar_senha_raises_auth_token_invalido_on_401(
    _configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.error

    def _fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", None, None
        )

    monkeypatch.setattr(
        "kairos.auth.supabase.urllib.request.urlopen", _fake_urlopen
    )

    with pytest.raises(supabase.AuthTokenInvalido):
        supabase.atualizar_senha("tok-expirado", "nova-senha-123")
