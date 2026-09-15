# Sub-aba Agenda com a lista real

## Descrição
Comportamentos 1, 2, 3: a sub-aba "Agenda" da ficha deixa de mostrar "em breve" (o marcador some da sub-nav) e passa a listar as sessões agendadas do aluno em ordem cronológica; sem sessões, mostra um estado vazio com o botão "Agendar sessão".

## Depende de
02-agenda-servico

## Especificação funcional
- `GET /alunos/{id}/agenda` deixa de mostrar o `.coming-soon` e passa a listar as sessões agendadas do aluno (data DD/MM/AAAA, hora HH:MM, tipo, duração), em ordem cronológica, dentro da ficha (cabeçalho + sub-nav).
- Na sub-nav, a sub-aba "Agenda" perde o marcador "em breve" (Feedback/Financeiro mantêm).
- Estado vazio: sem sessões, mostra uma frase e um botão "Agendar sessão" → `/alunos/{id}/agenda/nova` (rota criada na issue 04; até lá o botão 404, esperado no meio da fatia).
- Duração NULL → "sem registro"; observação, se houver, aparece como linha secundária; id de aluno inexistente → 404.

## Pré-condições
- Issues 01 e 02 concluídas: `list_sessoes` no serviço; `ficha_layout` e `ficha_header`; `get_aluno`. É o mesmo molde da sub-aba de Avaliações (`kairos/avaliacoes/routes.py` + `templates/avaliacoes/lista.html`). 249 testes verdes.

## Arquivos a criar
- `kairos/agenda/routes.py` — `APIRouter`; `GET /alunos/{aluno_id}/agenda`: `get_aluno` (404 se None) + `list_sessoes` → renderiza `agenda/lista.html` com `ficha_header(aluno)`, `subtab='agenda'`, e as sessões formatadas por um helper privado `_to_list_display(s)` (data DD/MM/AAAA, hora HH:MM, tipo com rótulo "Individual"/"Grupo", duração "N min" ou "sem registro", observação ou None, id).
- `kairos/templates/agenda/lista.html` — `{% extends "alunos/ficha_layout.html" %}`; no bloco: botão "Agendar sessão" no topo; se há sessões, uma lista (reusa `.card-list`/`.card`) com data · hora · tipo · duração (+ observação); senão o estado vazio "Ainda não há sessões agendadas." + o botão.
- `tests/test_agenda_lista.py` — sem sessões → estado vazio + botão "Agendar sessão"; Agenda ativa e sem "em breve"; com sessões (criadas via service) mostra-as em ordem cronológica com data/hora/tipo; duração NULL → "sem registro"; `/alunos/999/agenda` → 404.

## Arquivos a modificar
- `kairos/alunos/routes.py` — REMOVER a rota `aluno_agenda` (`GET /alunos/{aluno_id}/agenda`); o módulo agenda assume-a. `_render_ficha` continua para perfil/feedback/financeiro.
- `kairos/templates/alunos/ficha_layout.html` — na sub-nav, tirar o `<span class="soon">em breve</span>` do link Agenda (linha 31).
- `kairos/main.py` — `from kairos.agenda.routes import router as agenda_router` + `app.include_router(agenda_router)`.
- `kairos/static/css/components.css` — só se precisar (reusar `.card`/`.card-list`).

## Camadas envolvidas
aplicação (rotas agenda + ajustes alunos/main), frontend (lista + ficha_layout), teste

## Status
concluída
