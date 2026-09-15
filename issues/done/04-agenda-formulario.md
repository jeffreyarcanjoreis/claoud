# Formulário de agendar sessão

## Descrição
Comportamentos 4, 5, 6, 7, 8 (lado da UI): formulário para agendar uma sessão do aluno (data, hora, duração opcional, tipo, observação opcional); submeter válido cria a sessão e ela aparece na agenda; data/hora em falta, tipo inválido ou duração não-positiva → 400 com mensagem, sem gravar; campos opcionais vazios ficam NULL.

## Depende de
03-agenda-subaba-lista

## Especificação funcional
- `GET /alunos/{id}/agenda/nova` mostra o formulário de nova sessão (dentro da ficha, sub-aba Agenda ativa): data, hora, duração (opcional), tipo (select individual/grupo), observação (opcional).
- `POST /alunos/{id}/agenda` com dados válidos cria a sessão e redireciona (303) para `/alunos/{id}/agenda`; a sessão passa a aparecer na lista.
- Sem data, sem hora, tipo inválido, ou duração não-positiva → 400, re-render do formulário com a mensagem e os valores digitados preservados; nada gravado.
- Campos opcionais vazios ficam NULL. id de aluno inexistente (GET ou POST) → 404.

## Pré-condições
- Issue 03 concluída: `agenda/routes.py`, `create_sessao` no serviço, o botão "Agendar sessão" na lista, o `ficha_layout`. Mesmo molde do formulário de Avaliações.

## Arquivos a criar
- `kairos/templates/agenda/nova.html` — `{% extends "alunos/ficha_layout.html" %}`; formulário `method="post" action="/alunos/{id}/agenda"`: data (`<input type="date">`), hora (`<input type="time">`), duração (`<input type="number" min="1">`, opcional), tipo (`<select>` com Individual="individual" / Grupo="grupo"), observação (`<textarea>`), botão "Agendar". Exibe `error` e preserva `values`.
- `tests/test_agenda_formulario.py` — GET nova → 200 com o form (campos data/hora/tipo); POST válido → 303 e a sessão aparece na lista (via list_sessoes/o HTML); POST sem data → 400, nada gravado, valores preservados; POST sem hora → 400; POST tipo inválido → 400; POST duração 0/negativa → 400; duração vazia → NULL; `/alunos/999/agenda/nova` → 404; POST em aluno inexistente → 404.

## Arquivos a modificar
- `kairos/agenda/routes.py` — adicionar `GET /alunos/{aluno_id}/agenda/nova` (get_aluno→404; renderiza nova.html com header + subtab='agenda') e `POST /alunos/{aluno_id}/agenda` (get_aluno→404; recebe os campos via `Form`; `create_sessao(aluno_id, ...)`; `ValidationError` → re-render nova.html 400 com `error`/`values`; sucesso → RedirectResponse 303 para a lista). ATENÇÃO à ordem: registar `/agenda/nova` (literal) ANTES de qualquer `/agenda/{sessao_id}...` (issue 05). `sessao_id` será int; "nova" é literal.
- `kairos/static/css/components.css` — só se preciso (o padrão de formulário já existe).

## Camadas envolvidas
aplicação (rotas GET/POST de agenda), frontend (nova.html), teste

## Status
concluída
