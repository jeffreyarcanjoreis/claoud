"""Tests for issue 29 (Fase 2.1 of the login epic): the "email" column on
alunos and the auto-link-by-email at the student's first login.

Covers the functional specification:
- the "alunos.email" column is normalized on write (create and update):
  stripped and lowercased, empty/whitespace-only becomes NULL;
- ``find_alunos_by_email`` matches active students case-insensitively,
  returns an empty list for an unknown or blank e-mail, and never returns an
  inactive student;
- converting a lead (Contato) into a student derives the e-mail from the
  lead's "contato" field only when it looks like an e-mail (contains "@" and
  no whitespace); a phone number never becomes a fabricated e-mail, while
  the "contact" field still carries the raw lead contact either way;
- ``resolver_papel_no_login`` keeps its two original rules unchanged (an
  existing Perfil's stored role wins; the very first login ever bootstraps
  as "coach") and adds the auto-link-by-email rule: once a coach exists, a
  login whose e-mail matches exactly one active, not-yet-linked Aluno
  creates a Perfil(papel="aluno", aluno_id=...) and returns "aluno"; zero or
  more than one match, an Aluno that already has a Perfil, or an inactive
  Aluno all return None and create nothing;
- the coach's "ficha" page (GET /alunos/{id}) shows an access-status badge
  derived from the e-mail/Perfil combination: "Sem e-mail", "Aguardando 1º
  login" or "Acesso ativo".

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows. Only the tests that exercise
the real ``/login`` route are marked ``@pytest.mark.real_auth``; every other
test calls ``kairos.alunos.service`` / ``kairos.auth.service`` /
``kairos.contatos.service`` directly (no network, no HTTP).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno, find_alunos_by_email, get_aluno, update_aluno
from kairos.auth import service as auth_service
from kairos.contatos.service import converter_contato_em_aluno, create_contato
from kairos.main import app
from kairos.migrations_runner import run_migrations


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# 1. Column / normalization (create_aluno, update_aluno)
# ---------------------------------------------------------------------------


def test_create_aluno_normalizes_email_strip_and_lowercase(data_dir: Path) -> None:
    run_migrations()

    aluno = create_aluno(name="Maria Silva", email=" Foo@Bar.COM ")

    assert aluno["email"] == "foo@bar.com"


def test_create_aluno_blank_email_becomes_none(data_dir: Path) -> None:
    run_migrations()

    aluno = create_aluno(name="Maria Silva", email="")

    assert aluno["email"] is None


def test_update_aluno_normalizes_email_strip_and_lowercase(data_dir: Path) -> None:
    run_migrations()
    aluno = create_aluno(name="Maria Silva", email="original@x.com")

    updated = update_aluno(aluno["id"], name="Maria Silva", email=" Novo@Email.COM ")

    assert updated is not None
    assert updated["email"] == "novo@email.com"


def test_update_aluno_blank_email_clears_it_to_none(data_dir: Path) -> None:
    run_migrations()
    aluno = create_aluno(name="Maria Silva", email="original@x.com")

    updated = update_aluno(aluno["id"], name="Maria Silva", email="")

    assert updated is not None
    assert updated["email"] is None


# ---------------------------------------------------------------------------
# 2. find_alunos_by_email
# ---------------------------------------------------------------------------


def test_find_alunos_by_email_matches_active_aluno_case_insensitively(
    data_dir: Path,
) -> None:
    run_migrations()
    create_aluno(name="Maria Silva", email="ana@x.com")

    found = find_alunos_by_email("ANA@X.COM")

    assert len(found) == 1
    assert found[0]["name"] == "Maria Silva"


def test_find_alunos_by_email_returns_empty_list_for_unknown_email(
    data_dir: Path,
) -> None:
    run_migrations()
    create_aluno(name="Maria Silva", email="ana@x.com")

    assert find_alunos_by_email("desconhecido@x.com") == []


def test_find_alunos_by_email_returns_empty_list_for_blank_email(
    data_dir: Path,
) -> None:
    run_migrations()

    assert find_alunos_by_email("") == []
    assert find_alunos_by_email("   ") == []


def test_find_alunos_by_email_excludes_inactive_aluno(data_dir: Path) -> None:
    run_migrations()
    create_aluno(name="Maria Silva", email="ana@x.com", status="inactive")

    assert find_alunos_by_email("ana@x.com") == []


# ---------------------------------------------------------------------------
# 3. Lead -> aluno conversion derives (or not) the e-mail
# ---------------------------------------------------------------------------


def test_converter_contato_with_email_like_contact_fills_aluno_email(
    data_dir: Path,
) -> None:
    run_migrations()
    contato = create_contato(nome="Maria Silva", contato="maria@x.com")

    aluno_id = converter_contato_em_aluno(contato["id"])
    aluno = get_aluno(aluno_id)

    assert aluno is not None
    assert aluno["email"] == "maria@x.com"
    assert aluno["contact"] == "maria@x.com"


def test_converter_contato_with_phone_contact_leaves_aluno_email_none(
    data_dir: Path,
) -> None:
    run_migrations()
    contato = create_contato(nome="João Souza", contato="11999998888")

    aluno_id = converter_contato_em_aluno(contato["id"])
    aluno = get_aluno(aluno_id)

    assert aluno is not None
    assert aluno["email"] is None
    assert aluno["contact"] == "11999998888"


# ---------------------------------------------------------------------------
# 4. resolver_papel_no_login: original rules stay unchanged
# ---------------------------------------------------------------------------


def test_resolver_bootstraps_first_ever_login_as_coach(data_dir: Path) -> None:
    run_migrations()

    papel = auth_service.resolver_papel_no_login("uid-1", "qualquer@x.com")

    assert papel == "coach"
    perfil = auth_service.get_perfil("uid-1")
    assert perfil is not None
    assert perfil["papel"] == "coach"


def test_resolver_returns_existing_perfil_papel(data_dir: Path) -> None:
    run_migrations()
    auth_service.resolver_papel_no_login("uid-coach")  # bootstrap
    auth_service.criar_perfil(user_id="uid-2", papel="aluno")

    papel = auth_service.resolver_papel_no_login("uid-2", "qualquer@x.com")

    assert papel == "aluno"


# ---------------------------------------------------------------------------
# 5. resolver: auto-link by e-mail (the new rule)
# ---------------------------------------------------------------------------


def test_resolver_links_aluno_by_matching_email_and_creates_perfil(
    data_dir: Path,
) -> None:
    run_migrations()
    auth_service.resolver_papel_no_login("uid-coach")  # bootstrap an existing coach
    aluno = create_aluno(name="Maria Silva", email="aluno@x.com")

    papel = auth_service.resolver_papel_no_login("uid-aluno", "Aluno@X.com")

    assert papel == "aluno"
    perfil = auth_service.get_perfil("uid-aluno")
    assert perfil is not None
    assert perfil["papel"] == "aluno"
    assert perfil["aluno_id"] == aluno["id"]

    perfil_by_aluno = auth_service.get_perfil_by_aluno(aluno["id"])
    assert perfil_by_aluno is not None
    assert perfil_by_aluno["user_id"] == "uid-aluno"


# ---------------------------------------------------------------------------
# 6. resolver: e-mail with no match
# ---------------------------------------------------------------------------


def test_resolver_returns_none_when_no_aluno_matches_the_email(
    data_dir: Path,
) -> None:
    run_migrations()
    auth_service.resolver_papel_no_login("uid-coach")  # bootstrap an existing coach

    papel = auth_service.resolver_papel_no_login("uid-x", "ninguem@x.com")

    assert papel is None
    assert auth_service.get_perfil("uid-x") is None


# ---------------------------------------------------------------------------
# 7. resolver: ambiguous e-mail (2+ active alunos)
# ---------------------------------------------------------------------------


def test_resolver_returns_none_and_creates_nothing_when_email_is_ambiguous(
    data_dir: Path,
) -> None:
    run_migrations()
    auth_service.resolver_papel_no_login("uid-coach")  # bootstrap an existing coach
    aluno1 = create_aluno(name="Maria Silva", email="dup@x.com")
    aluno2 = create_aluno(name="Mariana Souza", email="dup@x.com")

    papel = auth_service.resolver_papel_no_login("uid-y", "dup@x.com")

    assert papel is None
    assert auth_service.get_perfil("uid-y") is None
    assert auth_service.get_perfil_by_aluno(aluno1["id"]) is None
    assert auth_service.get_perfil_by_aluno(aluno2["id"]) is None


# ---------------------------------------------------------------------------
# 8. resolver: aluno already linked to a Perfil is not relinked
# ---------------------------------------------------------------------------


def test_resolver_does_not_relink_aluno_that_already_has_a_perfil(
    data_dir: Path,
) -> None:
    run_migrations()
    auth_service.resolver_papel_no_login("uid-coach")  # bootstrap an existing coach
    aluno = create_aluno(name="Maria Silva", email="ligada@x.com")
    primeiro_papel = auth_service.resolver_papel_no_login("uid-first", "ligada@x.com")
    assert primeiro_papel == "aluno"  # sanity check: the first login did link

    papel = auth_service.resolver_papel_no_login("uid-second", "ligada@x.com")

    assert papel is None
    assert auth_service.get_perfil("uid-second") is None
    perfil_by_aluno = auth_service.get_perfil_by_aluno(aluno["id"])
    assert perfil_by_aluno is not None
    assert perfil_by_aluno["user_id"] == "uid-first"


# ---------------------------------------------------------------------------
# 9. resolver: inactive aluno never links
# ---------------------------------------------------------------------------


def test_resolver_does_not_link_inactive_aluno_with_matching_email(
    data_dir: Path,
) -> None:
    run_migrations()
    auth_service.resolver_papel_no_login("uid-coach")  # bootstrap an existing coach
    aluno = create_aluno(name="Maria Silva", email="inativa@x.com", status="inactive")

    papel = auth_service.resolver_papel_no_login("uid-z", "inativa@x.com")

    assert papel is None
    assert auth_service.get_perfil_by_aluno(aluno["id"]) is None


# ---------------------------------------------------------------------------
# 10. Access-status badge on the coach's "ficha" page (GET /alunos/{id})
# ---------------------------------------------------------------------------


def test_ficha_shows_sem_email_badge_when_aluno_has_no_email(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    assert "Sem e-mail" in response.text


def test_ficha_shows_aguardando_login_badge_when_email_has_no_perfil(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva", email="maria@x.com")

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    assert "Aguardando 1º login" in response.text


def test_ficha_shows_acesso_ativo_badge_when_aluno_has_a_perfil(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva", email="maria@x.com")
        auth_service.criar_perfil(
            user_id="uid-1", papel="aluno", aluno_id=aluno["id"]
        )

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    assert "Acesso ativo" in response.text


def test_ficha_shows_the_email_text_itself(data_dir: Path) -> None:
    # Regressão: o campo "E-mail" da ficha usa aluno.email_display (não uma
    # variável de topo), então o e-mail gravado precisa aparecer na página.
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva", email="maria@x.com")

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    assert "maria@x.com" in response.text
