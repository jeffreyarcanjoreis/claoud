# Alunos no visual da marca

## Descrição
Comportamentos 6 e 11 do SPEC: as telas de Alunos que já existem (lista, perfil, novo, editar, _form, nao_encontrado) passam a aparecer dentro do shell, no visual da marca; um campo vazio continua a mostrar "sem registro" (regra 6), agora no estilo da marca. Nenhum comportamento de backend muda; os testes de Alunos continuam verdes.

## Depende de
02-shell-painel

## Especificação funcional
- As telas de Alunos (lista, perfil, novo, editar, 404) aparecem no visual completo da marca, sobre o shell: cartões com o nome em Fraunces, selo de status (Ativo em ouro / Inativo apagado), objetivo e período legíveis, e hover no cartão usando o easing dos tokens.
- No perfil, os campos aparecem como uma lista de definições (rótulo em clay maiúsculo + valor); um campo vazio mostra "sem registro" em itálico na cor sálvia.
- Os formulários (novo/editar) têm campos com estado de foco dourado e o botão principal como pílula dourada (hover em argila); a barra de filtros e os links ficam no tom da marca.
- As mensagens de erro aparecem em argila e as de sucesso em tom que contrasta, legíveis sobre o fundo escuro.
- A página 404 (aluno não encontrado) aparece no visual da marca.
- Casos de borda: nenhum texto verificado pelos testes muda (rótulos, valores e "sem registro" continuam presentes) — os 80 testes continuam verdes. Nenhum comportamento de backend muda.

## Pré-condições
- Issues 01 e 02 concluídas: tokens.css, base.css e shell.css carregados; o shell envolve o conteúdo num `<main class="content">`.
- O sentinela de campo vazio é a string "sem registro" (definida em routes.py como `_NO_RECORD`), já entregue nos campos `*_display`.

## Arquivos a criar
- `kairos/static/css/components.css` — estilos de marca para os componentes de Alunos, usando as custom properties de tokens.css: `.card-list`/`.card`/`.card-header`/`.card-title`/`.card-line` (cartão da lista, nome em Fraunces, hover com `--ease`), `.badge`/`.badge-active`/`.badge-inactive`, `.filter-bar`, `.button-link` e `button`/inputs (foco dourado, botão pílula), `.message-success`/`.message-error`, a lista de definições do perfil (`.profile`/`.row`/`.k`/`.v`), e `.none` ("sem registro" itálico sálvia).
- `tests/test_alunos_marca.py` — verifica: (a) `GET /static/css/components.css` → 200 e a página `/alunos` tem o `<link>` para ele; (b) no perfil de um aluno com campos vazios, cada "sem registro" vem dentro de um elemento com classe `none`; (c) o cartão da lista tem o `badge` com a classe de status (badge-active/badge-inactive).

## Arquivos a modificar
- `kairos/templates/base.html` — adicionar `<link rel="stylesheet" href="/static/css/components.css">` (depois de shell.css).
- `kairos/templates/alunos/perfil.html` — reestruturar os campos numa lista de definições (`.profile` com `.row` → `.k` rótulo + `.v` valor); envolver o valor num `<span class="none">` quando for igual ao sentinela "sem registro" (usar `{% set NONE = "sem registro" %}` no topo e comparar; lógica de apresentação, sem tocar em rotas). Manter exatamente os mesmos rótulos e valores.
- `kairos/templates/alunos/lista.html` — ajustes mínimos de marcação apenas se necessário; o visual do cartão vem sobretudo via CSS nas classes já existentes.
- `kairos/templates/alunos/_form.html`, `novo.html`, `editar.html`, `nao_encontrado.html` — ajustes mínimos de marcação se necessário; o visual vem via CSS. Não alterar textos nem campos.

## Camadas envolvidas
frontend (CSS + templates de Alunos), teste

## Status
concluída
