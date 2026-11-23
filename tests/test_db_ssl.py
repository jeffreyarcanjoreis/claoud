"""Conexão criptografada com o Postgres em produção (kairos.db.connect_args).

Em produção a conexão com o Postgres usa TLS, para que dados dos alunos
(inclusive de saúde) e a senha do banco nunca trafeguem em texto puro.
SQLite e execuções fora de produção não mudam; KAIROS_DATABASE_SSL força
ou desliga a criptografia.
"""

import ssl

import pytest

from kairos import db

_PG = "postgresql+pg8000://u:p@db.example.com:5432/postgres"
_SQLITE = "sqlite:////tmp/kairos.db"


@pytest.fixture(autouse=True)
def _env_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("KAIROS_ENV", "RENDER", "KAIROS_DATABASE_SSL"):
        monkeypatch.delenv(var, raising=False)


def _tem_tls(args: dict) -> bool:
    contexto = args.get("ssl_context")
    return isinstance(contexto, ssl.SSLContext)


def test_sqlite_nunca_usa_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIROS_ENV", "production")
    assert db.connect_args(_SQLITE) == {}


def test_postgres_fora_de_producao_sem_tls() -> None:
    assert db.connect_args(_PG) == {}


def test_postgres_em_producao_usa_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIROS_ENV", "production")
    args = db.connect_args(_PG)
    assert _tem_tls(args)
    # Criptografado (sslmode=require); o certificado do Supabase não é
    # verificado contra a cadeia do sistema.
    assert args["ssl_context"].verify_mode == ssl.CERT_NONE
    assert args["ssl_context"].check_hostname is False


def test_postgres_no_render_usa_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    assert _tem_tls(db.connect_args(_PG))


def test_disable_desliga_tls_em_producao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIROS_ENV", "production")
    monkeypatch.setenv("KAIROS_DATABASE_SSL", "disable")
    assert db.connect_args(_PG) == {}


def test_require_liga_tls_fora_de_producao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIROS_DATABASE_SSL", "require")
    assert _tem_tls(db.connect_args(_PG))


def test_valor_invalido_cai_no_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIROS_DATABASE_SSL", "talvez")
    assert db.connect_args(_PG) == {}
    monkeypatch.setenv("KAIROS_ENV", "production")
    assert _tem_tls(db.connect_args(_PG))


def test_get_engine_repassa_as_opcoes(monkeypatch: pytest.MonkeyPatch) -> None:
    """O engine do app é criado com as opções de conexão (TLS em produção)."""
    monkeypatch.setenv("KAIROS_ENV", "production")
    monkeypatch.setenv("KAIROS_DATABASE_URL", "postgresql://u:p@db.example.com:5432/postgres")
    capturado = {}

    def falso_create_engine(url, **kwargs):
        capturado["url"] = url
        capturado.update(kwargs)
        raise RuntimeError("parar antes de conectar")

    monkeypatch.setattr(db, "create_engine", falso_create_engine)
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_engine_url", None)
    with pytest.raises(RuntimeError, match="parar antes de conectar"):
        db.get_engine()
    assert capturado["url"].startswith("postgresql+pg8000://")
    assert _tem_tls(capturado["connect_args"])
