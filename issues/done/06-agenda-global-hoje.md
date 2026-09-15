# Agenda global de hoje + tile do Início

## Descrição
Comportamentos 10, 11, 12: uma página /agenda (nível painel) mostra as sessões de hoje de todos os alunos (nome do aluno, hora, tipo) em ordem de hora, com estado vazio quando não há; o tile "Sessões de hoje" do Início mostra o número real e liga a /agenda.

## Depende de
02-agenda-servico

## Especificação funcional
- `GET /agenda` (nível painel) mostra as sessões de HOJE de todos os alunos, cada uma com o nome do aluno, a hora (HH:MM) e o tipo (Individual/Grupo), em ordem de hora.
- Cada sessão na visão de hoje liga à agenda do aluno (`/alunos/{aluno_id}/agenda`).
- Quando não há sessões hoje, `/agenda` mostra um estado vazio ("Nenhuma sessão hoje.").
- No Início, o tile "Sessões de hoje" deixa de mostrar "em breve" e passa a mostrar o **número real** de sessões de hoje (0 se não houver — dado real, regra 6) e vira um link para `/agenda`.
- "Hoje" = a data de hoje do servidor.
- 268 testes verdes; nenhum comportamento anterior muda.

## Pré-condições
- Issues 01-05 concluídas: `SessaoAgendada`, `list_sessoes`, o módulo agenda, o Início (`painel/routes.py` + `inicio.html`) com `counts`. 268 testes verdes.

## Arquivos a criar
- `kairos/templates/painel/agenda.html` — `{% extends "base.html" %}`; eyebrow + `<h1>Agenda de hoje</h1>`; se há sessões, uma lista (reusa `.card-list`/`.card`) onde cada item é um link para `/alunos/{{ s.aluno_id }}/agenda` mostrando `{{ s.aluno_nome }} · {{ s.hora }} · {{ s.tipo_label }}`; senão o estado vazio "Nenhuma sessão hoje.".
- `tests/test_agenda_global.py` — sem sessões hoje: `GET /agenda` → 200, estado vazio; com 2 sessões de HOJE (criadas via service com `data` = hoje) de alunos diferentes → aparecem com nome/hora/tipo, em ordem de hora, e cada uma linka para `/alunos/{aluno_id}/agenda`; uma sessão de OUTRO dia NÃO aparece em /agenda; o tile "Sessões de hoje" do Início mostra o número real (ex.: cria 2 hoje → o Início mostra "2" e um link para `/agenda`), e já não mostra "em breve".

## Arquivos a modificar
- `kairos/agenda/service.py` — `sessoes_de_hoje() -> list[dict]`: `select(SessaoAgendada, Aluno.name).join(Aluno, SessaoAgendada.aluno_id == Aluno.id).where(SessaoAgendada.data == datetime.date.today()).order_by(SessaoAgendada.hora.asc(), SessaoAgendada.id.asc())`; devolve `{aluno_id, aluno_nome, hora, tipo}` (importar `Aluno` de `kairos.alunos.models`). `contar_sessoes_de_hoje() -> int` (count com o mesmo filtro de data). Leitura, sem log.
- `kairos/painel/routes.py` — adicionar `GET /agenda` (`response_class=HTMLResponse`) que chama `sessoes_de_hoje()`, formata cada uma (hora HH:MM, tipo_label) e renderiza `painel/agenda.html`; e na rota do Início, acrescentar `counts["sessoes_hoje"] = contar_sessoes_de_hoje()`.
- `kairos/templates/painel/inicio.html` — trocar o tile "Sessões de hoje" de `<div class="stat">...em breve...</div>` para `<a class="stat" href="/agenda"><div class="n">{{ counts.sessoes_hoje }}</div><div class="l">Sessões de hoje</div></a>`.

## Camadas envolvidas
serviço (sessões de hoje), aplicação (rota /agenda + Início), frontend (agenda.html + tile), teste

## Status
concluída
