"""Tests for issue 16: living proportions of the session arc.

Service (``set_proporcoes``, ``reset_proporcoes``, ``set_duracao`` reset,
``arco_da_sessao`` override + ``ajustado``), coach routes and student view.

Isolation: KAIROS_DATA_DIR points at a tmp_path; conftest auto-logs in as coach.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.migrations_runner import run_migrations
from kairos.treinos.service import (
    FASE_OPCOES,
    ValidationError,
    arco_da_sessao,
    create_treino,
    get_treino,
    reset_proporcoes,
    set_duracao,
    set_proporcoes,
)

CANON_45 = [4, 7, 11, 16, 7]
CANON_60 = [5, 9, 15, 22, 9]
VALID_45 = {
    "preparacao": 6,
    "aquecimento": 6,
    "skill": 10,
    "apice": 18,
    "volta_a_calma": 5,
}
VALID_45_LIST = [6, 6, 10, 18, 5]
MIN_COLS = [f"min_{f}" for f in FASE_OPCOES]


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    run_migrations()
    yield target
    kairos.db.dispose_engine()


@pytest.fixture
def treino(data_dir: Path) -> dict:
    aluno = create_aluno(name="Ana")
    t = create_treino(aluno["id"], nome="Treino A")
    set_duracao(t["id"], 45)
    return t


def _minutos(treino_id: int) -> list[int]:
    return [p["minutos"] for p in arco_da_sessao(treino_id)]


def _ajustados(treino_id: int) -> list[bool]:
    return [p["ajustado"] for p in arco_da_sessao(treino_id)]


def _cols_none(treino_id: int) -> bool:
    t = get_treino(treino_id)
    return all(t[c] is None for c in MIN_COLS)


# --------------------------------------------------------------------------- #
# 1. set_proporcoes                                                            #
# --------------------------------------------------------------------------- #


def test_set_proporcoes_persists_and_arco_reflects_minutes(treino: dict) -> None:
    result = set_proporcoes(treino["id"], VALID_45)

    assert result is not None
    assert [result[c] for c in MIN_COLS] == VALID_45_LIST
    assert [get_treino(treino["id"])[c] for c in MIN_COLS] == VALID_45_LIST
    assert _minutos(treino["id"]) == VALID_45_LIST
    assert sum(_minutos(treino["id"])) == 45


def test_set_proporcoes_marks_ajustado_only_on_changed_phases(treino: dict) -> None:
    set_proporcoes(treino["id"], VALID_45)

    # canonical 45: [4, 7, 11, 16, 7] vs [6, 6, 10, 18, 5] -> all differ
    assert _ajustados(treino["id"]) == [True, True, True, True, True]

    # keep two phases equal to canonical
    set_proporcoes(
        treino["id"],
        {"preparacao": 4, "aquecimento": 7, "skill": 12, "apice": 15, "volta_a_calma": 7},
    )
    assert _ajustados(treino["id"]) == [False, False, True, True, False]


def test_set_proporcoes_exposes_arco_ajustado_flag(treino: dict) -> None:
    assert get_treino(treino["id"])["arco_ajustado"] is False

    result = set_proporcoes(treino["id"], VALID_45)

    assert result["arco_ajustado"] is True
    assert get_treino(treino["id"])["arco_ajustado"] is True


def test_set_proporcoes_accepts_numeric_strings(treino: dict) -> None:
    minutos = {k: str(v) for k, v in VALID_45.items()}

    set_proporcoes(treino["id"], minutos)

    assert _minutos(treino["id"]) == VALID_45_LIST


def test_arco_without_override_is_canonical_and_not_ajustado(treino: dict) -> None:
    assert _minutos(treino["id"]) == CANON_45
    assert _ajustados(treino["id"]) == [False] * 5


# --------------------------------------------------------------------------- #
# 2. set_proporcoes validation                                                 #
# --------------------------------------------------------------------------- #


def test_set_proporcoes_wrong_sum_raises_and_persists_nothing(treino: dict) -> None:
    bad = {"preparacao": 5, "aquecimento": 5, "skill": 10, "apice": 15, "volta_a_calma": 5}
    assert sum(bad.values()) == 40

    with pytest.raises(ValidationError, match="45"):
        set_proporcoes(treino["id"], bad)

    assert _cols_none(treino["id"])
    assert _minutos(treino["id"]) == CANON_45
    assert _ajustados(treino["id"]) == [False] * 5


def test_set_proporcoes_wrong_sum_message_mentions_total(treino: dict) -> None:
    bad = {"preparacao": 5, "aquecimento": 5, "skill": 10, "apice": 15, "volta_a_calma": 5}

    with pytest.raises(ValidationError) as exc:
        set_proporcoes(treino["id"], bad)

    assert "somar 45" in str(exc.value)
    assert "40" in str(exc.value)


@pytest.mark.parametrize("bad_value", [0, -3, "", "abc", None, "1.5"])
def test_set_proporcoes_invalid_phase_raises_and_persists_nothing(
    treino: dict, bad_value
) -> None:
    minutos = dict(VALID_45)
    minutos["skill"] = bad_value

    with pytest.raises(ValidationError):
        set_proporcoes(treino["id"], minutos)

    assert _cols_none(treino["id"])
    assert _minutos(treino["id"]) == CANON_45


def test_set_proporcoes_phase_below_one_with_correct_sum_raises(treino: dict) -> None:
    # sums to 45 but one phase is 0
    minutos = {"preparacao": 0, "aquecimento": 10, "skill": 10, "apice": 20, "volta_a_calma": 5}
    assert sum(minutos.values()) == 45

    with pytest.raises(ValidationError):
        set_proporcoes(treino["id"], minutos)

    assert _cols_none(treino["id"])


def test_set_proporcoes_missing_phase_raises_and_persists_nothing(
    treino: dict,
) -> None:
    minutos = dict(VALID_45)
    del minutos["apice"]

    with pytest.raises(ValidationError):
        set_proporcoes(treino["id"], minutos)

    assert _cols_none(treino["id"])


def test_set_proporcoes_without_duracao_raises(data_dir: Path) -> None:
    aluno = create_aluno(name="Ana")
    t = create_treino(aluno["id"], nome="Sem duracao")

    with pytest.raises(ValidationError, match="Defina a duração"):
        set_proporcoes(t["id"], VALID_45)

    assert _cols_none(t["id"])


def test_set_proporcoes_unknown_treino_returns_none(data_dir: Path) -> None:
    assert set_proporcoes(9999, VALID_45) is None


def test_invalid_attempt_keeps_previous_override(treino: dict) -> None:
    set_proporcoes(treino["id"], VALID_45)
    bad = dict(VALID_45, skill=11)

    with pytest.raises(ValidationError):
        set_proporcoes(treino["id"], bad)

    assert _minutos(treino["id"]) == VALID_45_LIST


# --------------------------------------------------------------------------- #
# 3. reset_proporcoes                                                          #
# --------------------------------------------------------------------------- #


def test_reset_proporcoes_returns_arco_to_canonical(treino: dict) -> None:
    set_proporcoes(treino["id"], VALID_45)

    result = reset_proporcoes(treino["id"])

    assert result is not None
    assert result["arco_ajustado"] is False
    assert _cols_none(treino["id"])
    assert _minutos(treino["id"]) == CANON_45
    assert _ajustados(treino["id"]) == [False] * 5
    assert get_treino(treino["id"])["arco_ajustado"] is False


def test_reset_proporcoes_without_override_is_harmless(treino: dict) -> None:
    result = reset_proporcoes(treino["id"])

    assert result is not None
    assert _minutos(treino["id"]) == CANON_45


def test_reset_proporcoes_unknown_treino_returns_none(data_dir: Path) -> None:
    assert reset_proporcoes(9999) is None


# --------------------------------------------------------------------------- #
# 4. set_duracao resets the override                                           #
# --------------------------------------------------------------------------- #


def test_set_duracao_change_resets_override(treino: dict) -> None:
    set_proporcoes(treino["id"], VALID_45)

    set_duracao(treino["id"], 60)

    assert _cols_none(treino["id"])
    assert _minutos(treino["id"]) == CANON_60
    assert _ajustados(treino["id"]) == [False] * 5
    assert get_treino(treino["id"])["arco_ajustado"] is False


def test_set_duracao_same_value_keeps_override(treino: dict) -> None:
    set_proporcoes(treino["id"], VALID_45)

    set_duracao(treino["id"], 45)
    set_duracao(treino["id"], "45")

    assert _minutos(treino["id"]) == VALID_45_LIST
    assert [get_treino(treino["id"])[c] for c in MIN_COLS] == VALID_45_LIST


def test_set_duracao_same_value_twice_after_change_keeps_override(
    treino: dict,
) -> None:
    set_duracao(treino["id"], 60)
    set_proporcoes(
        treino["id"],
        {"preparacao": 6, "aquecimento": 9, "skill": 15, "apice": 21, "volta_a_calma": 9},
    )

    set_duracao(treino["id"], 60)

    assert _minutos(treino["id"]) == [6, 9, 15, 21, 9]


@pytest.mark.parametrize("empty", ["", None])
def test_set_duracao_clear_resets_override(treino: dict, empty) -> None:
    set_proporcoes(treino["id"], VALID_45)

    set_duracao(treino["id"], empty)

    assert get_treino(treino["id"])["duracao_min"] is None
    assert _cols_none(treino["id"])
    assert arco_da_sessao(treino["id"]) is None


def test_set_duracao_invalid_keeps_override(treino: dict) -> None:
    set_proporcoes(treino["id"], VALID_45)

    with pytest.raises(ValidationError):
        set_duracao(treino["id"], 50)

    assert _minutos(treino["id"]) == VALID_45_LIST


def test_override_after_duration_change_then_back_is_canonical(treino: dict) -> None:
    set_proporcoes(treino["id"], VALID_45)
    set_duracao(treino["id"], 60)
    set_duracao(treino["id"], 45)

    assert _minutos(treino["id"]) == CANON_45


# --------------------------------------------------------------------------- #
# 5. Coach routes                                                              #
# --------------------------------------------------------------------------- #


def _arco_minutes(html: str) -> list[int]:
    return [int(m) for m in re.findall(r'class="arco-fase-min">(\d+) min<', html)]


def _form(minutos: dict) -> dict:
    return {f"min_{k}": str(v) for k, v in minutos.items()}


def _post_prop(client: TestClient, aluno_id: int, treino_id: int, data: dict):
    return client.post(
        f"/alunos/{aluno_id}/treino/{treino_id}/proporcoes",
        data=data,
        follow_redirects=False,
    )


def _post_reset(client: TestClient, aluno_id: int, treino_id: int):
    return client.post(
        f"/alunos/{aluno_id}/treino/{treino_id}/proporcoes/resetar",
        follow_redirects=False,
    )


def test_post_proporcoes_valid_redirects_and_planilha_shows_adjusted(
    treino: dict,
) -> None:
    aluno_id = treino["aluno_id"]
    url = f"/alunos/{aluno_id}/treino/{treino['id']}"
    with TestClient(app) as client:
        response = _post_prop(client, aluno_id, treino["id"], _form(VALID_45))
        assert response.status_code == 303
        assert response.headers["location"] == url
        page = client.get(url)

    assert page.status_code == 200
    assert _minutos(treino["id"]) == VALID_45_LIST
    assert _arco_minutes(page.text) == VALID_45_LIST
    assert "is-ajustado" in page.text
    assert "arco-fase-tag" in page.text
    assert "voltar ao padrão" in page.text


def test_planilha_without_override_has_no_ajustado_mark(treino: dict) -> None:
    aluno_id = treino["aluno_id"]
    with TestClient(app) as client:
        page = client.get(f"/alunos/{aluno_id}/treino/{treino['id']}")

    assert _arco_minutes(page.text) == CANON_45
    assert 'class="arco-fase is-ajustado"' not in page.text
    assert '<span class="arco-fase-tag">' not in page.text
    assert "proporcoes" in page.text


def test_planilha_prefills_proporcoes_form_with_current_minutes(
    treino: dict,
) -> None:
    aluno_id = treino["aluno_id"]
    set_proporcoes(treino["id"], VALID_45)
    with TestClient(app) as client:
        page = client.get(f"/alunos/{aluno_id}/treino/{treino['id']}")

    for fase, minutos in VALID_45.items():
        assert re.search(
            rf'name="min_{fase}"[^>]*value="{minutos}"', page.text
        ), fase


def test_post_proporcoes_wrong_sum_returns_400_with_message_and_saves_nothing(
    treino: dict,
) -> None:
    aluno_id = treino["aluno_id"]
    bad = {"preparacao": 5, "aquecimento": 5, "skill": 10, "apice": 15, "volta_a_calma": 5}
    with TestClient(app) as client:
        response = _post_prop(client, aluno_id, treino["id"], _form(bad))

    assert response.status_code == 400
    assert "devem somar 45 min (somaram 40)" in response.text
    assert _cols_none(treino["id"])
    assert _minutos(treino["id"]) == CANON_45


@pytest.mark.parametrize("bad_value", ["0", "", "abc"])
def test_post_proporcoes_invalid_phase_returns_400_and_saves_nothing(
    treino: dict, bad_value: str
) -> None:
    aluno_id = treino["aluno_id"]
    data = _form(VALID_45)
    data["min_skill"] = bad_value
    with TestClient(app) as client:
        response = _post_prop(client, aluno_id, treino["id"], data)

    assert response.status_code == 400
    assert _cols_none(treino["id"])


def test_post_proporcoes_without_duracao_returns_400(data_dir: Path) -> None:
    aluno = create_aluno(name="Ana")
    t = create_treino(aluno["id"], nome="Sem duracao")
    with TestClient(app) as client:
        response = _post_prop(client, aluno["id"], t["id"], _form(VALID_45))

    assert response.status_code == 400
    assert "Defina a duração" in response.text
    assert _cols_none(t["id"])


def test_post_resetar_redirects_and_restores_canonical(treino: dict) -> None:
    aluno_id = treino["aluno_id"]
    url = f"/alunos/{aluno_id}/treino/{treino['id']}"
    set_proporcoes(treino["id"], VALID_45)
    with TestClient(app) as client:
        response = _post_reset(client, aluno_id, treino["id"])
        assert response.status_code == 303
        assert response.headers["location"] == url
        page = client.get(url)

    assert _cols_none(treino["id"])
    assert _arco_minutes(page.text) == CANON_45
    assert "is-ajustado" not in page.text


def test_reset_button_hidden_without_override(treino: dict) -> None:
    with TestClient(app) as client:
        page = client.get(f"/alunos/{treino['aluno_id']}/treino/{treino['id']}")

    assert "voltar ao padrão" not in page.text


def test_proporcoes_routes_404_for_another_alunos_treino(data_dir: Path) -> None:
    dono = create_aluno(name="Dono")
    outro = create_aluno(name="Outro")
    t = create_treino(dono["id"], nome="Do dono")
    set_duracao(t["id"], 45)
    with TestClient(app) as client:
        r1 = _post_prop(client, outro["id"], t["id"], _form(VALID_45))
        set_proporcoes(t["id"], VALID_45)
        r2 = _post_reset(client, outro["id"], t["id"])

    assert r1.status_code == 404
    assert r2.status_code == 404
    # the owner's override was neither created by r1 nor wiped by r2
    assert _minutos(t["id"]) == VALID_45_LIST


def test_proporcoes_routes_404_for_missing_treino_or_aluno(treino: dict) -> None:
    with TestClient(app) as client:
        r1 = _post_prop(client, treino["aluno_id"], 9999, _form(VALID_45))
        r2 = _post_reset(client, treino["aluno_id"], 9999)
        r3 = _post_prop(client, 9999, treino["id"], _form(VALID_45))
        r4 = _post_reset(client, 9999, treino["id"])

    assert [r.status_code for r in (r1, r2, r3, r4)] == [404] * 4
    assert _cols_none(treino["id"])


# --------------------------------------------------------------------------- #
# 6. Student sees the adjustment                                               #
# --------------------------------------------------------------------------- #


def _login_as_aluno(monkeypatch: pytest.MonkeyPatch, aluno_id) -> None:
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)


def test_aluno_sees_adjusted_minutes_in_arco(
    treino: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    aluno_id = treino["aluno_id"]
    with TestClient(app) as client:
        # coach adjusts (auto-login as coach)
        response = _post_prop(client, aluno_id, treino["id"], _form(VALID_45))
        assert response.status_code == 303
        # then act as the owning student
        _login_as_aluno(monkeypatch, aluno_id)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.status_code == 200
    assert 'class="arco"' in page.text
    assert _arco_minutes(page.text) == VALID_45_LIST
    # read-only: no proportions form for the student
    assert "/proporcoes" not in page.text
    assert "Salvar proporções" not in page.text


def test_aluno_sees_canonical_again_after_coach_resets(
    treino: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    aluno_id = treino["aluno_id"]
    set_proporcoes(treino["id"], VALID_45)
    with TestClient(app) as client:
        _post_reset(client, aluno_id, treino["id"])
        _login_as_aluno(monkeypatch, aluno_id)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert _arco_minutes(page.text) == CANON_45
