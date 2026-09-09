"""FastAPI application entry point for Kairos."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from kairos import config
from kairos.acompanhamento.routes import router as acompanhamento_router
from kairos.agenda.routes import router as agenda_router
from kairos.alunos.routes import router as alunos_router
from kairos.area_aluno.routes import router as area_aluno_router
from kairos.auth.middleware import AuthGateMiddleware
from kairos.auth.routes import router as auth_router
from kairos.avaliacoes.routes import router as avaliacoes_router
from kairos.checkin.routes import router as checkin_router
from kairos.contatos.routes import router as contatos_router
from kairos.financeiro.routes import router as financeiro_router
from kairos.log import setup_logging
from kairos.mensagens.routes import router as mensagens_router
from kairos.migrations_runner import run_migrations
from kairos.painel.routes import router as painel_router
from kairos.registro_treino.routes import router as registro_treino_router
from kairos.tarefas.routes import router as tarefas_router
from kairos.treinos.routes import router as treinos_router
from kairos.vitrine.routes import router as vitrine_router

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: configure logging and migrate the database.

    Migration errors propagate and abort startup on purpose (project rule:
    errors are never swallowed).
    """
    setup_logging()
    run_migrations()
    if config.dev_no_auth():
        logger.warning(
            "KAIROS_DEV_NO_AUTH ATIVO: autenticacao DESLIGADA (modo dev) — "
            "todas as areas abrem sem login. NAO use em producao."
        )
    logger.info("Kairos application started.")
    yield


app = FastAPI(title="Kairos", lifespan=lifespan)

# Middleware order matters: Starlette wraps requests outside-in in reverse
# registration order, so the *last* `add_middleware` call runs *first*.
# `SessionMiddleware` must run before `AuthGateMiddleware` (the gate reads
# `request.session`), so it is added last here.
app.add_middleware(AuthGateMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.secret_key(),
    same_site="lax",
    https_only=False,
)

app.include_router(auth_router)
app.include_router(painel_router)
app.include_router(alunos_router)
app.include_router(area_aluno_router)
app.include_router(avaliacoes_router)
app.include_router(checkin_router)
app.include_router(contatos_router)
app.include_router(financeiro_router)
app.include_router(mensagens_router)
app.include_router(acompanhamento_router)
app.include_router(agenda_router)
app.include_router(registro_treino_router)
app.include_router(tarefas_router)
app.include_router(treinos_router)
app.include_router(vitrine_router)

_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check endpoint."""
    return {"status": "ok"}
