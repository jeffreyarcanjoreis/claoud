"""Trava de configuração de produção (kairos.config.verificar_producao).

Em produção o app se recusa a iniciar com configuração insegura: login
desligado (KAIROS_DEV_NO_AUTH), sem segredo de sessão, sem banco na nuvem ou
sem Supabase. Fora de produção nada muda (o dev local mantém os fallbacks).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kairos import config

_ENV_PRODUCAO_OK = {
    "KAIROS_ENV": "production",
    "KAIROS_SECRET_KEY": "um-segredo-de-verdade",
    "KAIROS_DATABASE_URL": "postgresql://u:p@db.example.com:5432/postgres",
    "KAIROS_SUPABASE_URL": "https://ref.supabase.co",
    "KAIROS_SUPABASE_ANON_KEY": "anon-key",
}

_VARS = (
    "KAIROS_ENV",
    "RENDER",
    "KAIROS_DEV_NO_AUTH",
    "KAIROS_SECRET_KEY",
    "KAIROS_DATABASE_URL",
    "KAIROS_SUPABASE_URL",
    "KAIROS_SUPABASE_ANON_KEY",
)


@pytest.fixture(autouse=True)
def _env_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _VARS:
        monkeypatch.delenv(var, raising=False)


def _producao_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _ENV_PRODUCAO_OK.items():
        monkeypatch.setenv(key, value)


def test_producao_desligada_por_padrao() -> None:
    assert config.producao() is False


@pytest.mark.parametrize("valor", ["production", "PRODUCTION", "producao"])
def test_producao_por_kairos_env(monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
    monkeypatch.setenv("KAIROS_ENV", valor)
    assert config.producao() is True


def test_producao_detectada_no_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    assert config.producao() is True


def test_outro_kairos_env_nao_e_producao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIROS_ENV", "development")
    assert config.producao() is False


def test_fora_de_producao_nao_trava_nem_com_dev_no_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KAIROS_DEV_NO_AUTH", "1")
    config.verificar_producao()  # não levanta


def test_producao_bem_configurada_inicia(monkeypatch: pytest.MonkeyPatch) -> None:
    _producao_ok(monkeypatch)
    config.verificar_producao()  # não levanta


@pytest.mark.parametrize(
    ("ajuste", "trecho"),
    [
        (("KAIROS_DEV_NO_AUTH", "1"), "KAIROS_DEV_NO_AUTH"),
        (("KAIROS_SECRET_KEY", None), "KAIROS_SECRET_KEY"),
        (("KAIROS_SECRET_KEY", "   "), "KAIROS_SECRET_KEY"),
        (("KAIROS_DATABASE_URL", None), "KAIROS_DATABASE_URL"),
        (("KAIROS_SUPABASE_URL", None), "KAIROS_SUPABASE_URL"),
        (("KAIROS_SUPABASE_ANON_KEY", None), "KAIROS_SUPABASE_ANON_KEY"),
    ],
)
def test_cada_problema_trava_o_startup(
    monkeypatch: pytest.MonkeyPatch, ajuste: tuple, trecho: str
) -> None:
    _producao_ok(monkeypatch)
    var, valor = ajuste
    if valor is None:
        monkeypatch.delenv(var)
    else:
        monkeypatch.setenv(var, valor)
    with pytest.raises(RuntimeError, match=trecho):
        config.verificar_producao()


def test_segredo_padrao_de_dev_conta_como_ausente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _producao_ok(monkeypatch)
    monkeypatch.setenv("KAIROS_SECRET_KEY", config._DEV_INSECURE_SECRET_KEY)
    with pytest.raises(RuntimeError, match="KAIROS_SECRET_KEY"):
        config.verificar_producao()


def test_lista_todos_os_problemas_de_uma_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIROS_ENV", "production")
    monkeypatch.setenv("KAIROS_DEV_NO_AUTH", "1")
    with pytest.raises(RuntimeError) as exc:
        config.verificar_producao()
    mensagem = str(exc.value)
    for var in (
        "KAIROS_DEV_NO_AUTH",
        "KAIROS_SECRET_KEY",
        "KAIROS_DATABASE_URL",
        "KAIROS_SUPABASE_URL",
    ):
        assert var in mensagem


def test_app_nao_sobe_em_producao_insegura(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A trava roda no startup, antes das migrações: nada é criado no disco."""
    monkeypatch.setenv("KAIROS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KAIROS_ENV", "production")
    monkeypatch.setenv("KAIROS_DEV_NO_AUTH", "1")
    from kairos.main import app

    with pytest.raises(RuntimeError, match="KAIROS_DEV_NO_AUTH"):
        with TestClient(app):
            pass
    assert not (tmp_path / "kairos.db").exists()
