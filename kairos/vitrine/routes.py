"""HTTP routes (application layer) for the "vitrine" (public showcase)
domain.

Thin routes only: they render templates with no business rules. Displayed
texts are in Portuguese (architecture rule 10) and live in the template, not
here.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from kairos.contatos.routes import cadastro_opcoes_context
from kairos.web import templates

router = APIRouter()


@router.get("/vitrine", response_class=HTMLResponse)
async def hero(request: Request) -> HTMLResponse:
    """Render the public showcase's opening (hero) page.

    Includes the sign-up form's fixed select options (sex, conditioning
    level, weekly frequency) so the modal (AJAX) version of the Avaliação
    Inicial can render the same choices as the ``/comecar`` full page.
    """
    return templates.TemplateResponse(
        request, "vitrine/hero.html", {**cadastro_opcoes_context()}
    )
