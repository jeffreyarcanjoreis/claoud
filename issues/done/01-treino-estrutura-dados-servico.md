# Estrutura do treino — fase no item + serviço

## Descrição
Cada exercício do treino passa a ter uma fase da sessão (Preparação, Aquecimento, Skill, Ápice, Volta à calma) e uma observação do coach. A camada de dados/serviço ganha: a fase no item (validada contra as 5), a observação por item, o vocabulário fixo das fases (nome + pergunta-guia), a apresentação do treino (texto do coach), e um agrupamento dos itens nas 5 fases na ordem canônica (+ "Sem fase"). Comportamentos [F1] 1, 2, 6, 9 (serviço), e a base de 3/4/5/7.

## Depende de
nenhuma

## Status
concluída

## Especificação funcional
Tudo no domínio `treinos` (reaproveita o máximo do que já existe). Descobertas da pesquisa: `add_item_to_treino` **já aceita e grava `observacao`** e `get_treino_detail` **já devolve `observacao`** por item — a observação por exercício já está pronta no serviço; só a **fase** é nova. A apresentação do treino = `Treino.observacao` (já existe no modelo, em `create_treino` e em `_treino_to_dict`); falta só uma mutação para **editar** depois da criação.

- **Fase no item:** `TreinoItem` ganha a coluna `fase` (`String(20)`, nullable). NULL = "Sem fase" (regra 6). Valores validados no serviço, não no banco.
- **Vocabulário fixo (fonte única, no serviço de treinos):**
  - `FASE_OPCOES = ("preparacao", "aquecimento", "skill", "apice", "volta_a_calma")` (ordem canônica).
  - `FASE_LABELS = {preparacao:"Preparação", aquecimento:"Aquecimento", skill:"Skill", apice:"Ápice", volta_a_calma:"Volta à calma"}`.
  - `FASE_PERGUNTAS = {preparacao:"Quem chegou hoje?", aquecimento:"O corpo está aqui agora?", skill:"Este corpo está pronto?", apice:"Qual o limite de hoje?", volta_a_calma:"O que mudou?"}`.
- **`add_item_to_treino`** ganha o parâmetro `fase` (Optional[str]): normaliza vazio→None (válido = "Sem fase"); se preenchido e não ∈ `FASE_OPCOES` → `ValidationError("Fase inválida.")` (nada gravado). Grava `item.fase`; loga (regra 8). Os demais campos (exercicio_id, series, reps, carga, observacao) seguem como estão.
- **Dicts de item** (o resultado de `add_item_to_treino` e cada item de `get_treino_detail`) passam a incluir `fase` e `fase_label` (`FASE_LABELS.get(fase)` ou None).
- **Agrupamento** — nova função pura `agrupar_itens_por_fase(itens)` → lista na **ordem canônica**: para cada fase em `FASE_OPCOES`, um grupo `{fase, fase_label, fase_pergunta, itens:[...]}` (mesmo vazio — comportamento 4); ao fim, um grupo `{fase:None, fase_label:"Sem fase", fase_pergunta:None, itens:[...]}` **só quando houver** itens sem fase. Recebe a lista `itens` do `get_treino_detail` (não reconsulta o banco). Reusada pelas rotas do coach (issue 02) e do aluno (issue 03).
- **Apresentação:** nova mutação `set_apresentacao(treino_id, texto)` — normaliza (vazio→None = "sem registro", regra 6); grava `treino.observacao`; loga; retorna o dict do treino, ou None se o treino não existe (a rota trata 404). (`create_treino` já grava observacao; esta permite editar depois.)

Casos de borda: fase fora do conjunto → recusada sem gravar; fase "—"/vazia → None ("Sem fase"); dentro de cada fase os itens seguem a `ordem` já existente (comportamento 6); agrupamento com nenhum item → 5 grupos vazios, sem "Sem fase".

## Pré-condições
- Domínio `treinos` (modelo `Treino`/`TreinoItem`/`Exercicio`, serviço, `get_treino_detail`) existe. HEAD de migração: **0024**.

## Arquivos a criar
- `migrations/versions/0025_add_fase_to_treino_itens.py` — `upgrade()` adiciona `fase` (`String(20)`, nullable) a `treino_itens`; `downgrade()` remove. `down_revision = "0024"`. Tipos portáveis; sem default (NULL = Sem fase).

## Arquivos a modificar
- `kairos/treinos/models.py` — adicionar `fase: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)` em `TreinoItem`.
- `kairos/treinos/service.py` — constantes `FASE_OPCOES`/`FASE_LABELS`/`FASE_PERGUNTAS`; parâmetro `fase` em `add_item_to_treino` (validação); `fase`/`fase_label` nos dicts de item (add + `get_treino_detail`); função `agrupar_itens_por_fase(itens)`; função `set_apresentacao(treino_id, texto)`.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): coluna `fase` em `TreinoItem` + migração 0025.
- **serviço** (`servico-writer`): vocabulário das fases, `fase` em `add_item_to_treino` + nos dicts, `agrupar_itens_por_fase`, `set_apresentacao`.
- **testes** (`teste-writer`): `tests/test_treino_fase.py` — `add_item_to_treino` com fase válida/ inválida/ vazia; `fase`/`fase_label` no `get_treino_detail`; `agrupar_itens_por_fase` (ordem canônica, fases vazias presentes, "Sem fase" só quando há item sem fase, ordem interna preservada); `set_apresentacao` (grava, limpa com vazio, treino inexistente → None). Bump de `HEAD_REVISION` 0024→0025 nos testes que fixam a head. Suíte anterior verde.
