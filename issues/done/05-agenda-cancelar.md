# Cancelar uma sessão

## Descrição
Comportamento 9: um botão/ação "cancelar" em cada sessão da agenda do aluno remove a sessão agendada; ela deixa de aparecer na lista.

## Depende de
04-agenda-formulario

## Especificação funcional
- Cada sessão na agenda do aluno tem uma ação "cancelar" (um pequeno formulário POST com um botão, não um link — cancelar altera estado).
- `POST /alunos/{aluno_id}/agenda/{sessao_id}/cancelar` remove a sessão e redireciona (303) para `/alunos/{aluno_id}/agenda`; a sessão deixa de aparecer.
- Segurança/coerência: se a sessão não existe, ou não pertence a esse aluno → 404 (não cancela sessão de outro aluno pela URL errada).
- Aluno inexistente → 404.

## Pré-condições
- Issue 04 concluída: há como agendar; `agenda/routes.py`, `cancel_sessao`, `get_sessao`, a `lista.html`.

## Arquivos a modificar
- `kairos/agenda/routes.py` — adicionar `POST /alunos/{aluno_id}/agenda/{sessao_id}/cancelar` (`sessao_id: int`): `get_aluno` (404 se None); `s = get_sessao(sessao_id)`; se `s is None` ou `s["aluno_id"] != aluno_id` → 404; senão `cancel_sessao(sessao_id)` e RedirectResponse 303 para `/alunos/{aluno_id}/agenda`. Registada DEPOIS de `/agenda/nova`.
- `kairos/templates/agenda/lista.html` — em cada sessão, acrescentar um `<form method="post" action="/alunos/{{ aluno.id }}/agenda/{{ s.id }}/cancelar" class="cancelar-form"><button type="submit" class="btn-cancelar">Cancelar</button></form>`. (O `s.id` já vem do `_to_list_display`.)
- `kairos/static/css/components.css` — estilo discreto do `.btn-cancelar` (link-like / botão pequeno, cor `--bone-dim` → `--clay` no hover), só tokens.

## Arquivos a criar
- `tests/test_agenda_cancelar.py` — cria aluno + sessão (via service ou POST); a lista mostra o botão/form de cancelar apontando para a rota certa; `POST /alunos/{id}/agenda/{sessao_id}/cancelar` → 303 e a sessão deixa de aparecer (list_sessoes vazia); `POST` de sessao_id inexistente → 404; `POST` de uma sessão de OUTRO aluno pela URL de um aluno → 404 (isolamento); aluno inexistente → 404.

## Camadas envolvidas
aplicação (rota de cancelar), frontend (botão na lista + css), teste

## Status
concluída
