"""Shared web resources for the Kairos application layer.

Holds the single Jinja2Templates instance used by all routers, pointing at
the ``kairos/templates`` directory resolved from this file's location so it
works regardless of the current working directory.
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Cache-busting token for static assets. Computed once at import (i.e. per
# server start): stable within a run so browsers cache normally, but changes on
# each restart/deploy so a new CSS/JS is fetched instead of a stale cached copy.
# Templates append it as `?v={{ asset_ver }}` on <link>/<script> URLs.
templates.env.globals["asset_ver"] = str(int(time.time()))

_STATUS_LABELS = {"active": "Ativo", "inactive": "Inativo"}
_STATUS_CLASSES = {"active": "badge-active", "inactive": "badge-inactive"}


def ficha_header(aluno: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer aluno dict to the "ficha" page header fields.

    Shared by every sub-tab route (perfil, avaliações, feedback, agenda,
    financeiro) so the status label/class mapping lives in a single place.
    """
    return {
        "id": aluno["id"],
        "name": aluno["name"],
        "status_label": _STATUS_LABELS.get(aluno["status"], aluno["status"]),
        "status_class": _STATUS_CLASSES.get(aluno["status"], "badge-inactive"),
        "foto": aluno.get("foto"),
    }


def formatar_reais(valor: Optional[Any]) -> str:
    """Format a monetary value as Brazilian Real ("R$ 1.234,50").

    ``None`` means no data (architecture rule 6: never a fake default), and
    is rendered as "sem registro".
    """
    if valor is None:
        return "sem registro"
    s = f"{valor:,.2f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {s}"
