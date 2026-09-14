# Editar exercício do treino in-place (coach)

## Descrição
Na planilha do coach, editar um exercício sem remover e adicionar de novo: séries, reps, carga, observação e a fase (mudar a fase de um item = editar o campo fase). Comportamentos [F+] 11 e 13.

## Depende de
nenhuma (a coluna fase já existe; serviço de treino já existe)

## Status
concluída

## Especificação funcional
O exercício em si (qual exercício da biblioteca) e a `ordem` **não** mudam na edição — só a prescrição e a fase. Reaproveita validações já existentes (`_parse_series`, `_parse_fase`, `_normalize`).

- **Serviço `update_item(item_id, *, series=None, reps=None, carga=None, observacao=None, fase=None)`:** valida `series` (positivo se dado) e `fase` (∈ `FASE_OPCOES` ou vazio→None) ANTES de tocar o banco (erro → `ValidationError`, nada gravado); normaliza reps/carga/observacao (vazio→None, regra 6); dentro de `session_scope` busca o `TreinoItem`, se None retorna None (rota trata 404); atualiza os campos; loga (regra 8); retorna o dict do item (com `fase`/`fase_label`).
- **Rota `GET /alunos/{aluno_id}/treino/{treino_id}/itens/{item_id}/editar`:** get-or-404 no padrão atual (aluno existe; treino é do aluno; item é do treino — senão `_aluno_nao_encontrado`). Usa `get_treino_detail` para achar o item (já traz exercicio_nome, series, reps, carga, observacao, fase). Renderiza um formulário de edição pré-preenchido, com o nome do exercício (fixo, não editável) e o `<select>` de fase (opção atual marcada).
- **Rota `POST /alunos/{aluno_id}/treino/{treino_id}/itens/{item_id}`:** mesmos get-or-404; `update_item(...)`; `ValidationError` → re-render do form de edição com a mensagem (status 400); sucesso → `RedirectResponse` 303 para `/alunos/{aluno_id}/treino/{treino_id}`.
- **Planilha:** cada linha de exercício ganha um link/botão "Editar" que leva ao `GET .../editar` (ao lado do "Remover" atual).

Casos de borda: item de outro treino/aluno ou inexistente → 404; fase inválida / séries não-positiva → 400 sem gravar; campos vazios → NULL.

## Pré-condições
- Fatia estrutura (01–03) concluída. `treinos/service.py` (com `FASE_OPCOES`, `_parse_fase`, `_parse_series`), `treino_detail` e `treinos/aluno_detalhe.html` existem. HEAD de migração 0025 (esta issue NÃO mexe em schema).

## Arquivos a criar
- `kairos/templates/treinos/item_editar.html` — formulário de edição do item (estende `alunos/ficha_layout.html`): nome do exercício (fixo), campos séries/reps/carga/observação, `<select name="fase">`; botão salvar; link cancelar de volta à planilha.

## Arquivos a modificar
- `kairos/treinos/service.py` — nova função `update_item(...)`.
- `kairos/treinos/routes.py` — rotas `GET .../itens/{item_id}/editar` e `POST .../itens/{item_id}` (importa `update_item`; reusa `_FASE_OPCOES_DISPLAY`, `ficha_header`, `get_treino_detail`).
- `kairos/templates/treinos/aluno_detalhe.html` — botão "Editar" em cada linha de exercício (junto do "Remover").

## Camadas envolvidas
- **serviço** (`servico-writer`): `update_item`.
- **aplicação** (`aplicacao-writer`): rotas de editar (GET form + POST update).
- **frontend** (`frontend-writer`): `item_editar.html` + botão editar na planilha.
- **testes** (`teste-writer`): `tests/test_treino_editar_item.py` — GET edit form 200 pré-preenchido; POST edita séries/reps/carga/observação/fase (confirma via get_treino_detail); fase inválida/séries inválida → 400 sem gravar; item de outro aluno → 404. Suíte anterior verde.
