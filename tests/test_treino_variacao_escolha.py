"""Tests for issue 08: the student choosing "meu lugar hoje" among the
variations described by the coach (base/regressão/progressão).

Covers the functional specification:

- ``escolher_variacao(item_id, escolha)``: valid choices ("base",
  "regressao", "progressao") persist and are reflected by
  ``get_treino_detail`` (value + label); an invalid choice raises
  ``ValidationError`` and persists nothing; a blank/None choice on an item
  that already had one clears it back to ``None`` (rule 6 -- "ainda não me
  reconheci"); a nonexistent item returns ``None``; the chosen variation is
  not required to have a description from the coach (rule: the student
  recognizes themself regardless of what the coach wrote);
- ``get_treino_detail``: an item without a choice exposes
  ``variacao_escolhida`` and ``variacao_escolhida_label`` as ``None`` (no
  fabricated default);
- the aluno's route (``POST /aluno/treinos/{treino_id}/itens/{item_id}/
  variacao``): a valid ``escolha`` persists and redirects (303) back to the
  workout page, reflected on the next GET; an empty ``escolha`` clears the
  choice; a tampered (out-of-range) ``escolha`` is a no-op -- redirects
  without changing anything, never a 500; another aluno's workout, or an
  item that doesn't belong to the workout in the URL, -> 404 (never 403);
- the student's own read-only planilha (``area_aluno/treino_detalhe.html``):
  the "Onde eu me reconheço hoje?" selector only appears when the coach
  described at least one variation, and the chosen option is visually
  marked (``is-escolhida`` / ``aria-pressed="true"``); with no variation
  described at all, the selector does not appear;
- the coach's planilha (``treinos/aluno_detalhe.html``): a read-only mirror
  line ("O aluno se reconheceu em: {label}") appears only when the student
  has chosen; otherwise nothing (rule 6 -- no fabricated feedback).

Isolation pattern shared with the other treino suites: KAIROS_DATA_DIR
points at a temp dir and the cached engine is disposed on setup/teardown
(see tests/test_treino_variacoes.py). The aluno-side login override follows
tests/test_treino_aluno_fases.py.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.treinos.service import (
    ValidationError,
    VARIACAO_LABELS,
    add_item_to_treino,
    create_exercicio,
    create_treino,
    escolher_variacao,
    get_treino_detail,
    update_item,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def _login_as_aluno(monkeypatch: pytest.MonkeyPatch, aluno_id) -> None:
    """Same pattern as tests/test_treino_aluno_fases.py: override the
    suite-wide auto-login-as-coach patch with a student session, patching
    both the gate's reference and the route module's directly-imported one.
    """
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)


# --------------------------------------------------------------------------- #
# 1. Service: escolher_variacao persists/clears/rejects                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("escolha", ["base", "regressao", "progressao"])
def test_escolher_variacao_persists_valid_choice_and_reflects_in_detail(
    data_dir: Path, escolha: str
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(
            item["id"],
            variacao_base="Base descrita",
            variacao_regressao="Regressão descrita",
            variacao_progressao="Progressão descrita",
        )

        result = escolher_variacao(item["id"], escolha)

        detail = get_treino_detail(treino["id"])

    assert result["variacao_escolhida"] == escolha
    assert result["variacao_escolhida_label"] == VARIACAO_LABELS[escolha]

    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_escolhida"] == escolha
    assert updated["variacao_escolhida_label"] == VARIACAO_LABELS[escolha]


def test_escolher_variacao_with_invalid_choice_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        with pytest.raises(ValidationError):
            escolher_variacao(item["id"], "xpto")

        detail = get_treino_detail(treino["id"])

    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_escolhida"] is None
    assert updated["variacao_escolhida_label"] is None


@pytest.mark.parametrize("blank_value", ["", "   ", None])
def test_escolher_variacao_with_blank_or_none_clears_existing_choice(
    data_dir: Path, blank_value
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        escolher_variacao(item["id"], "base")

        result = escolher_variacao(item["id"], blank_value)

        detail = get_treino_detail(treino["id"])

    assert result["variacao_escolhida"] is None
    assert result["variacao_escolhida_label"] is None
    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_escolhida"] is None
    assert updated["variacao_escolhida_label"] is None


def test_escolher_variacao_for_nonexistent_item_returns_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        result = escolher_variacao(9999, "base")

    assert result is None


def test_escolher_variacao_does_not_require_the_variation_to_be_described(
    data_dir: Path,
) -> None:
    """The student self-recognizes even in a variation the coach left blank
    -- the issue's spec: "não exige que a variação escolhida tenha
    descrição"."""
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        # No update_item call: no variation has been described by the coach.

        result = escolher_variacao(item["id"], "progressao")

    assert result["variacao_escolhida"] == "progressao"
    assert result["variacao_escolhida_label"] == "Progressão"


# --------------------------------------------------------------------------- #
# 2. get_treino_detail: item without a choice exposes None                  #
# --------------------------------------------------------------------------- #


def test_get_treino_detail_item_without_choice_exposes_none(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        detail = get_treino_detail(treino["id"])

    item = detail["itens"][0]
    assert item["variacao_escolhida"] is None
    assert item["variacao_escolhida_label"] is None


# --------------------------------------------------------------------------- #
# 3. Aluno route: POST .../variacao                                         #
# --------------------------------------------------------------------------- #


def test_post_variacao_with_valid_escolha_persists_and_redirects(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(item["id"], variacao_base="Base descrita")

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            f"/aluno/treinos/{treino['id']}/itens/{item['id']}/variacao",
            data={"escolha": "base"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/aluno/treinos/{treino['id']}"

        detail = get_treino_detail(treino["id"])
        pagina = client.get(f"/aluno/treinos/{treino['id']}")

    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_escolhida"] == "base"
    assert pagina.status_code == 200


def test_post_variacao_with_blank_escolha_clears_it(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(item["id"], variacao_base="Base descrita")
        escolher_variacao(item["id"], "base")

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            f"/aluno/treinos/{treino['id']}/itens/{item['id']}/variacao",
            data={"escolha": ""},
            follow_redirects=False,
        )

        assert response.status_code == 303

        detail = get_treino_detail(treino["id"])

    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_escolhida"] is None


def test_post_variacao_with_tampered_escolha_is_a_noop(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(item["id"], variacao_base="Base descrita")
        escolher_variacao(item["id"], "base")

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            f"/aluno/treinos/{treino['id']}/itens/{item['id']}/variacao",
            data={"escolha": "xpto"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/aluno/treinos/{treino['id']}"

        detail = get_treino_detail(treino["id"])

    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_escolhida"] == "base"  # unchanged


def test_post_variacao_on_another_alunos_treino_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        ex = create_exercicio(nome="Supino")
        treino_b = create_treino(aluno_b["id"], nome="Treino de B")
        item_b = add_item_to_treino(treino_b["id"], exercicio_id=str(ex["id"]))

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.post(
            f"/aluno/treinos/{treino_b['id']}/itens/{item_b['id']}/variacao",
            data={"escolha": "base"},
            follow_redirects=False,
        )

        assert response.status_code == 404

        detail = get_treino_detail(treino_b["id"])

    updated = next(i for i in detail["itens"] if i["id"] == item_b["id"])
    assert updated["variacao_escolhida"] is None


def test_post_variacao_for_item_not_belonging_to_treino_in_url_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino_a = create_treino(aluno["id"], nome="Treino A")
        treino_b = create_treino(aluno["id"], nome="Treino B")
        item_b = add_item_to_treino(treino_b["id"], exercicio_id=str(ex["id"]))

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            f"/aluno/treinos/{treino_a['id']}/itens/{item_b['id']}/variacao",
            data={"escolha": "base"},
            follow_redirects=False,
        )

        assert response.status_code == 404

        detail = get_treino_detail(treino_b["id"])

    updated = next(i for i in detail["itens"] if i["id"] == item_b["id"])
    assert updated["variacao_escolhida"] is None


# --------------------------------------------------------------------------- #
# 4. Aluno UI: selector only when a variation is described, choice marked   #
# --------------------------------------------------------------------------- #


def test_aluno_planilha_shows_selector_and_highlights_current_choice(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(item["id"], variacao_base="Supino reto com barra")
        escolher_variacao(item["id"], "base")

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 200
    assert "Onde eu me reconheço hoje" in response.text
    assert "is-escolhida" in response.text
    assert 'aria-pressed="true"' in response.text


def test_aluno_planilha_omits_selector_when_no_variation_described(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 200
    assert "Onde eu me reconheço hoje" not in response.text


# --------------------------------------------------------------------------- #
# 5. Coach UI: read-only mirror of the student's choice                     #
# --------------------------------------------------------------------------- #


def test_coach_planilha_shows_read_only_choice_when_aluno_has_chosen(
    data_dir: Path,
) -> None:
    """Spec (issue 08): the coach's planilha mirrors the student's choice
    read-only ("O aluno se reconheceu em: {label}").

    KNOWN PRODUCTION BUG (not fixed here, per instructions): this currently
    fails. ``kairos/treinos/routes.py``'s ``_to_item_display`` (used to
    build the dicts fed to ``treinos/aluno_detalhe.html``) was not updated
    by this slice to forward ``variacao_escolhida``/
    ``variacao_escolhida_label`` from ``get_treino_detail``'s item dicts, so
    ``i.variacao_escolhida`` is always Jinja ``Undefined`` (falsy) in that
    template, and the "O aluno se reconheceu em:" line never renders even
    when the student has chosen.
    """
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(item["id"], variacao_regressao="Supino com halteres")
        escolher_variacao(item["id"], "regressao")

        response = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert response.status_code == 200
    assert "O aluno se reconheceu em:" in response.text
    assert "Regressão" in response.text


def test_coach_planilha_omits_choice_line_when_aluno_has_not_chosen(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(item["id"], variacao_regressao="Supino com halteres")

        response = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert response.status_code == 200
    assert "O aluno se reconheceu em:" not in response.text
