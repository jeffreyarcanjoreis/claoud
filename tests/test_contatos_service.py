"""Tests for issue 20/22: the "contatos" (lightweight contact follow-up)
service layer.

Covers the functional specification:
- create_contato: a name is required (blank/whitespace-only -> ValidationError);
  empty "contato"/"observacao" normalize to None (never a fake default); a
  valid contact is born with status "a_contatar" (status is not accepted as
  input -- it comes from the column's server default); it is born with
  origem="manual" (the coach's manual quick-add path);
- create_cadastro (issue 22 -- native public sign-up form): nome and contato
  are required; consentimento must be True or the call raises
  ValidationError, and nothing is persisted; a valid submission persists the
  full profile (including health fields) and is born with
  origem="cadastro" and consentimento=True; idade out of the 1..120 range
  (or non-numeric) raises ValidationError; sexo/nivel_condicionamento/
  frequencia_desejada are validated against their fixed option sets; an
  empty optional field normalizes to None (never a fake default);
- list_contatos_abertos: returns only contacts whose status is in
  STATUS_ABERTOS ("a_contatar", "conversando"), excluding "virou_aluno" and
  "sem_interesse"; ordered most-recently-created first (created_at desc,
  id desc as a tie-breaker);
- get_contato: returns the contact as a dict, or None when the id does not
  exist;
- get_contato_detail: returns the contact as a dict augmented with
  Portuguese display labels (status_label, sexo_label, nivel_label,
  frequencia_label, origem_label), each None when the underlying coded
  field is None; None when the id does not exist;
- atualizar_status: an invalid status raises ValidationError; a
  non-existent id returns False without raising; a valid update actually
  changes the stored status and returns True;
- remover_contato: returns True and deletes the row when the id exists,
  False when it does not.
- converter_contato_em_aluno (issue 23): creates an Aluno mapping name<-nome,
  contact<-contato, sex<-sexo, age_reported<-idade, objective<-objetivo,
  weekly_frequency<-frequencia_desejada,
  conditioning_level<-nivel_condicionamento, restrictions<-lesoes,
  health_conditions<-condicoes and medications<-medicamentos; folds
  objetivos_secundarios, prazo_desejado and observacao (each only when
  present) plus a conversion-date line into the Aluno's notes; marks the
  Contato's status as "virou_aluno" (so it drops out of
  list_contatos_abertos); returns the new Aluno's id, or None when the
  Contato does not exist.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import get_aluno
from kairos.contatos.service import (
    STATUS_ABERTOS,
    STATUS_VALIDOS,
    ValidationError,
    atualizar_status,
    converter_contato_em_aluno,
    create_cadastro,
    create_contato,
    get_contato,
    get_contato_detail,
    list_contatos_abertos,
    remover_contato,
)
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
# create_contato
# ---------------------------------------------------------------------------


def test_create_contato_without_nome_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_contato(nome=None)

        with pytest.raises(ValidationError):
            create_contato(nome="   ")


def test_create_contato_with_empty_optional_fields_saves_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        contato = create_contato(nome="Ana Lima", contato="", observacao="")

    assert contato["contato"] is None
    assert contato["observacao"] is None


def test_create_contato_is_born_a_contatar(data_dir: Path) -> None:
    with TestClient(app):
        contato = create_contato(nome="Bruno Costa")

    assert contato["status"] == "a_contatar"
    assert contato["nome"] == "Bruno Costa"
    assert contato["id"] is not None
    assert contato["created_at"] is not None


def test_create_valid_contato_persists_all_fields(data_dir: Path) -> None:
    with TestClient(app):
        contato = create_contato(
            nome="Carla Souza",
            contato="(11) 99999-0000",
            observacao="Veio pelo Instagram",
        )

    assert contato["nome"] == "Carla Souza"
    assert contato["contato"] == "(11) 99999-0000"
    assert contato["observacao"] == "Veio pelo Instagram"


def test_create_contato_is_born_with_origem_manual(data_dir: Path) -> None:
    with TestClient(app):
        contato = create_contato(nome="Igor Lima")

    assert contato["origem"] == "manual"
    assert contato["consentimento"] is False


# ---------------------------------------------------------------------------
# create_cadastro
# ---------------------------------------------------------------------------


def test_create_cadastro_with_valid_data_persists_full_profile(
    data_dir: Path,
) -> None:
    with TestClient(app):
        contato = create_cadastro(
            nome="Julia Prado",
            contato="julia@example.com",
            idade="34",
            sexo="feminino",
            objetivo="Emagrecimento",
            objetivos_secundarios="Condicionamento geral",
            prazo_desejado="3 meses",
            frequencia_desejada="3-4",
            condicoes="Hipertensão controlada",
            lesoes="Joelho direito",
            medicamentos="Losartana",
            nivel_condicionamento="iniciante",
            consentimento=True,
        )

    assert contato["nome"] == "Julia Prado"
    assert contato["contato"] == "julia@example.com"
    assert contato["idade"] == 34
    assert contato["sexo"] == "feminino"
    assert contato["objetivo"] == "Emagrecimento"
    assert contato["objetivos_secundarios"] == "Condicionamento geral"
    assert contato["prazo_desejado"] == "3 meses"
    assert contato["frequencia_desejada"] == "3-4"
    assert contato["condicoes"] == "Hipertensão controlada"
    assert contato["lesoes"] == "Joelho direito"
    assert contato["medicamentos"] == "Losartana"
    assert contato["nivel_condicionamento"] == "iniciante"
    assert contato["consentimento"] is True
    assert contato["origem"] == "cadastro"
    assert contato["status"] == "a_contatar"


def test_create_cadastro_without_nome_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_cadastro(nome=None, contato="alguem@example.com", consentimento=True)

        with pytest.raises(ValidationError):
            create_cadastro(nome="   ", contato="alguem@example.com", consentimento=True)


def test_create_cadastro_without_contato_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_cadastro(nome="Karina Reis", contato=None, consentimento=True)

        with pytest.raises(ValidationError):
            create_cadastro(nome="Karina Reis", contato="   ", consentimento=True)


def test_create_cadastro_without_consentimento_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_cadastro(
                nome="Leandro Sousa",
                contato="leandro@example.com",
                consentimento=False,
            )


def test_create_cadastro_without_consentimento_persists_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_cadastro(
                nome="Marcia Teles",
                contato="marcia@example.com",
                consentimento=False,
            )

        assert list_contatos_abertos() == []


def test_create_cadastro_with_invalid_idade_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_cadastro(
                nome="Nadia Costa",
                contato="nadia@example.com",
                idade="0",
                consentimento=True,
            )

        with pytest.raises(ValidationError):
            create_cadastro(
                nome="Nadia Costa",
                contato="nadia@example.com",
                idade="121",
                consentimento=True,
            )

        with pytest.raises(ValidationError):
            create_cadastro(
                nome="Nadia Costa",
                contato="nadia@example.com",
                idade="abc",
                consentimento=True,
            )


def test_create_cadastro_with_invalid_sexo_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_cadastro(
                nome="Otavio Melo",
                contato="otavio@example.com",
                sexo="xpto",
                consentimento=True,
            )


def test_create_cadastro_with_invalid_nivel_condicionamento_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_cadastro(
                nome="Paula Vieira",
                contato="paula@example.com",
                nivel_condicionamento="xpto",
                consentimento=True,
            )


def test_create_cadastro_with_invalid_frequencia_desejada_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_cadastro(
                nome="Quintino Alves",
                contato="quintino@example.com",
                frequencia_desejada="xpto",
                consentimento=True,
            )


def test_create_cadastro_with_empty_optional_fields_saves_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        contato = create_cadastro(
            nome="Rita Farias",
            contato="rita@example.com",
            idade="",
            sexo="",
            objetivo="",
            objetivos_secundarios="",
            prazo_desejado="",
            frequencia_desejada="",
            condicoes="",
            lesoes="",
            medicamentos="",
            nivel_condicionamento="",
            consentimento=True,
        )

    assert contato["idade"] is None
    assert contato["sexo"] is None
    assert contato["objetivo"] is None
    assert contato["objetivos_secundarios"] is None
    assert contato["prazo_desejado"] is None
    assert contato["frequencia_desejada"] is None
    assert contato["condicoes"] is None
    assert contato["lesoes"] is None
    assert contato["medicamentos"] is None
    assert contato["nivel_condicionamento"] is None


# ---------------------------------------------------------------------------
# list_contatos_abertos
# ---------------------------------------------------------------------------


def test_list_contatos_abertos_orders_most_recent_first(data_dir: Path) -> None:
    with TestClient(app):
        create_contato(nome="Primeiro")
        create_contato(nome="Segundo")
        create_contato(nome="Terceiro")

        abertos = list_contatos_abertos()

    nomes = [c["nome"] for c in abertos]
    assert nomes == ["Terceiro", "Segundo", "Primeiro"]


def test_list_contatos_abertos_excludes_terminal_statuses(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_contato(nome="Virou aluno")
        desistiu = create_contato(nome="Sem interesse")
        ativo = create_contato(nome="Ainda em aberto")

        atualizar_status(aluno["id"], "virou_aluno")
        atualizar_status(desistiu["id"], "sem_interesse")

        abertos = list_contatos_abertos()

    nomes = [c["nome"] for c in abertos]
    assert nomes == ["Ainda em aberto"]


def test_list_contatos_abertos_empty_when_no_contacts(data_dir: Path) -> None:
    with TestClient(app):
        assert list_contatos_abertos() == []


# ---------------------------------------------------------------------------
# get_contato
# ---------------------------------------------------------------------------


def test_get_contato_returns_dict_for_existing_id(data_dir: Path) -> None:
    with TestClient(app):
        created = create_contato(nome="Diego Alves")

        loaded = get_contato(created["id"])

    assert loaded is not None
    assert loaded["nome"] == "Diego Alves"


def test_get_contato_returns_none_for_unknown_id(data_dir: Path) -> None:
    with TestClient(app):
        assert get_contato(9999) is None


# ---------------------------------------------------------------------------
# get_contato_detail
# ---------------------------------------------------------------------------


def test_get_contato_detail_returns_none_for_unknown_id(data_dir: Path) -> None:
    with TestClient(app):
        assert get_contato_detail(9999) is None


def test_get_contato_detail_includes_labels_for_a_cadastro_contact(
    data_dir: Path,
) -> None:
    with TestClient(app):
        created = create_cadastro(
            nome="Sonia Duarte",
            contato="sonia@example.com",
            sexo="feminino",
            frequencia_desejada="5+",
            nivel_condicionamento="avancado",
            consentimento=True,
        )

        detail = get_contato_detail(created["id"])

    assert detail is not None
    assert detail["status_label"] == "A contatar"
    assert detail["sexo_label"] == "Feminino"
    assert detail["nivel_label"] == "Avançado"
    assert detail["frequencia_label"] == "5+ dias"
    assert detail["origem_label"] == "Cadastro"


def test_get_contato_detail_labels_are_none_when_coded_fields_are_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        created = create_contato(nome="Tiago Rocha")

        detail = get_contato_detail(created["id"])

    assert detail is not None
    assert detail["status_label"] == "A contatar"
    assert detail["sexo_label"] is None
    assert detail["nivel_label"] is None
    assert detail["frequencia_label"] is None
    assert detail["origem_label"] == "Manual"


# ---------------------------------------------------------------------------
# atualizar_status
# ---------------------------------------------------------------------------


def test_atualizar_status_with_invalid_status_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        contato = create_contato(nome="Elis Regina")

        with pytest.raises(ValidationError):
            atualizar_status(contato["id"], "xpto")

        with pytest.raises(ValidationError):
            atualizar_status(contato["id"], None)


def test_atualizar_status_with_unknown_id_returns_false(data_dir: Path) -> None:
    with TestClient(app):
        result = atualizar_status(9999, "conversando")

    assert result is False


def test_atualizar_status_updates_the_stored_status(data_dir: Path) -> None:
    with TestClient(app):
        contato = create_contato(nome="Fabio Junior")

        result = atualizar_status(contato["id"], "conversando")

        loaded = get_contato(contato["id"])

    assert result is True
    assert loaded["status"] == "conversando"


def test_all_status_validos_are_accepted(data_dir: Path) -> None:
    with TestClient(app):
        contato = create_contato(nome="Giovana Reis")

        for valor in STATUS_VALIDOS:
            assert atualizar_status(contato["id"], valor) is True
            assert get_contato(contato["id"])["status"] == valor


def test_status_abertos_is_subset_of_status_validos() -> None:
    assert set(STATUS_ABERTOS) <= set(STATUS_VALIDOS)


# ---------------------------------------------------------------------------
# remover_contato
# ---------------------------------------------------------------------------


def test_remover_contato_returns_true_and_deletes_existing(data_dir: Path) -> None:
    with TestClient(app):
        contato = create_contato(nome="Helena Prado")

        result = remover_contato(contato["id"])

        assert get_contato(contato["id"]) is None

    assert result is True


def test_remover_contato_returns_false_for_unknown_id(data_dir: Path) -> None:
    with TestClient(app):
        result = remover_contato(9999)

    assert result is False


# ---------------------------------------------------------------------------
# converter_contato_em_aluno
# ---------------------------------------------------------------------------


def test_converter_contato_em_aluno_maps_every_dedicated_field(
    data_dir: Path,
) -> None:
    with TestClient(app):
        lead = create_cadastro(
            nome="Julia Prado",
            contato="julia@example.com",
            idade="34",
            sexo="feminino",
            objetivo="Emagrecimento",
            objetivos_secundarios="Condicionamento geral",
            prazo_desejado="3 meses",
            frequencia_desejada="3-4",
            condicoes="Hipertensão controlada",
            lesoes="Joelho direito",
            medicamentos="Losartana",
            nivel_condicionamento="iniciante",
            consentimento=True,
        )

        aluno_id = converter_contato_em_aluno(lead["id"])

        aluno = get_aluno(aluno_id)

    assert aluno_id is not None
    assert aluno is not None
    assert aluno["name"] == "Julia Prado"
    assert aluno["contact"] == "julia@example.com"
    assert aluno["sex"] == "feminino"
    assert aluno["age_reported"] == 34
    assert aluno["objective"] == "Emagrecimento"
    assert aluno["weekly_frequency"] == "3-4"
    assert aluno["conditioning_level"] == "iniciante"
    assert aluno["restrictions"] == "Joelho direito"
    assert aluno["health_conditions"] == "Hipertensão controlada"
    assert aluno["medications"] == "Losartana"
    assert aluno["status"] == "active"


def test_converter_contato_em_aluno_notes_include_the_unmapped_fields(
    data_dir: Path,
) -> None:
    with TestClient(app):
        lead = create_cadastro(
            nome="Julia Prado",
            contato="julia@example.com",
            objetivos_secundarios="Condicionamento geral",
            prazo_desejado="3 meses",
            consentimento=True,
        )

        aluno_id = converter_contato_em_aluno(lead["id"])
        aluno = get_aluno(aluno_id)

    today = datetime.date.today().strftime("%d/%m/%Y")
    assert aluno is not None
    assert "Objetivos secundários: Condicionamento geral" in aluno["notes"]
    assert "Prazo desejado: 3 meses" in aluno["notes"]
    assert f"Criado a partir do cadastro em {today}" in aluno["notes"]
    assert "Observação:" not in aluno["notes"]  # create_cadastro has no observacao


def test_converter_contato_em_aluno_notes_include_observacao_when_present(
    data_dir: Path,
) -> None:
    with TestClient(app):
        lead = create_contato(
            nome="Manual Lead", contato="manual@example.com", observacao="Prefere manhã"
        )

        aluno_id = converter_contato_em_aluno(lead["id"])
        aluno = get_aluno(aluno_id)

    assert aluno is not None
    assert "Observação: Prefere manhã" in aluno["notes"]
    assert "Objetivos secundários:" not in aluno["notes"]
    assert "Prazo desejado:" not in aluno["notes"]


def test_converter_contato_em_aluno_notes_only_has_conversion_date_when_nothing_else(
    data_dir: Path,
) -> None:
    with TestClient(app):
        lead = create_contato(nome="Sem Extras")

        aluno_id = converter_contato_em_aluno(lead["id"])
        aluno = get_aluno(aluno_id)

    today = datetime.date.today().strftime("%d/%m/%Y")
    assert aluno is not None
    assert aluno["notes"] == f"Criado a partir do cadastro em {today}"


def test_converter_contato_em_aluno_marks_lead_as_virou_aluno(
    data_dir: Path,
) -> None:
    with TestClient(app):
        lead = create_contato(nome="Convertida")

        converter_contato_em_aluno(lead["id"])

        loaded = get_contato(lead["id"])

    assert loaded is not None
    assert loaded["status"] == "virou_aluno"


def test_converter_contato_em_aluno_removes_lead_from_abertos_list(
    data_dir: Path,
) -> None:
    with TestClient(app):
        lead = create_contato(nome="Convertida")
        outra = create_contato(nome="Ainda em aberto")

        converter_contato_em_aluno(lead["id"])

        abertos = list_contatos_abertos()

    nomes = [c["nome"] for c in abertos]
    assert nomes == ["Ainda em aberto"]


def test_converter_contato_em_aluno_with_empty_optional_fields_maps_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        lead = create_contato(nome="Perfil Minimo")

        aluno_id = converter_contato_em_aluno(lead["id"])
        aluno = get_aluno(aluno_id)

    assert aluno is not None
    assert aluno["contact"] is None
    assert aluno["sex"] is None
    assert aluno["age_reported"] is None
    assert aluno["objective"] is None
    assert aluno["weekly_frequency"] is None
    assert aluno["conditioning_level"] is None
    assert aluno["restrictions"] is None
    assert aluno["health_conditions"] is None
    assert aluno["medications"] is None


def test_converter_contato_em_aluno_unknown_id_returns_none(data_dir: Path) -> None:
    with TestClient(app):
        result = converter_contato_em_aluno(9999)

    assert result is None
