# Reordenar exercícios dentro da fase (coach)

## Descrição
Na planilha do coach, o coach reordena os exercícios dentro de uma fase (mover para cima / para baixo), alterando a ordem em que aparecem. Comportamento [F+] 12.

## Depende de
nenhuma (usa a coluna `ordem` já existente)

## Status
concluída

## Especificação funcional
Reordenar por passos (mover ↑/↓), trocando a posição com o vizinho **da mesma fase**. Simples e testável; sem arrastar (drag) nesta fatia.

- **Serviço `mover_item(item_id, direcao)`:** `direcao` ∈ ("cima","baixo") — senão `ValidationError("Direção inválida.")`. Dentro de `session_scope`: busca o item; acha o **vizinho imediato na mesma fase e mesmo treino** na direção pedida (por `ordem`; "cima" = maior `ordem` que ainda é menor que a do item / o anterior; "baixo" = o próximo); se não há vizinho (item já é o primeiro/último da fase), no-op → retorna False. Caso haja, **troca os valores de `ordem`** entre os dois; loga; retorna True. Retorna False também quando o item não existe (a rota já faz get-or-404 antes).
- **Rota `POST /alunos/{aluno_id}/treino/{treino_id}/itens/{item_id}/mover`** (form `direcao`): get-or-404 no padrão atual (aluno, treino do aluno, item do treino); `mover_item(item_id, direcao)`; 303 de volta à planilha (no-op nas pontas também redireciona, sem erro).
- **Planilha (coach):** em cada linha, botões ↑ e ↓ (forms POST com `direcao=cima|baixo`) na coluna de ações, junto de Editar/Remover. Nas pontas o botão pode aparecer desabilitado ou simplesmente não fazer nada (no-op) — escolha o mais simples.

Casos de borda: mover o primeiro para cima / o último para baixo → no-op (303, nada muda); direção inválida (form adulterado) → tratar como no-op ou 400 (simples); item de outro aluno → 404.

## Pré-condições
- `treino_itens.ordem` existe; `agrupar_itens_por_fase` ordena por `ordem`. Fatia estrutura (01–03) e edição (04) concluídas. HEAD 0025 (sem schema novo).

## Arquivos a modificar
- `kairos/treinos/service.py` — `mover_item(item_id, direcao)`.
- `kairos/treinos/routes.py` — rota `POST .../itens/{item_id}/mover`.
- `kairos/templates/treinos/aluno_detalhe.html` — botões ↑/↓ por linha (dentro do bloco de fase).

## Camadas envolvidas
- **serviço** (`servico-writer`): `mover_item`.
- **aplicação** (`aplicacao-writer`): rota mover.
- **frontend** (`frontend-writer`): botões ↑/↓ na planilha.
- **testes** (`teste-writer`): `tests/test_treino_reordenar.py` — mover ↑/↓ troca a ordem com o vizinho da mesma fase (confirma via `get_treino_detail`); nas pontas é no-op; vizinho de outra fase não é afetado; item de outro aluno → 404. Suíte anterior verde.
