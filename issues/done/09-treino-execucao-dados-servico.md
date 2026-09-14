# Execução do aluno — dados + serviço

## Descrição
A base para o aluno registrar a execução de um exercício: marcar como feito, registrar carga/reps reais e uma observação da execução. Guarda por exercício (histórico por data); serviço para registrar e ler. Comportamentos [F+] 18 (dado do "feito"), 19, 20 (serviço).

## Depende de
nenhuma

## Status
concluída

## Especificação funcional
A execução é **por item do treino, por data**: uma linha por `(treino_item_id, data)` — o histórico é a sucessão de datas. Marcar/registrar de novo no mesmo dia **atualiza** a linha daquele dia (upsert); dias diferentes = linhas diferentes (histórico). Fidelidade ao método (regras 11–14): o registro é do aluno, sobre o que ele realmente fez; o "verbo é dele" na observação (regra 20). Regra 6: campos vazios = NULL = "sem registro".

Novo módulo de domínio `kairos/execucao/` (models + service), espelhando o estilo de `kairos/registro_treino/` e `kairos/nivel/`.

- **Dados (migração 0029):** tabela `execucoes_item` (model `ExecucaoItem`), tipos portáveis:
  - `id` PK autoincrement.
  - `treino_item_id` FK → `treino_itens.id`, `nullable=False`, `index=True`.
  - `data` `Date`, `nullable=False` (data da execução).
  - `feito` `Boolean`, `nullable=False` (o aluno marcou feito? definido explicitamente pelo serviço; sem default fabricado no banco).
  - `carga_real` `String(40)`, nullable.
  - `reps_real` `String(40)`, nullable.
  - `observacao` `Text`, nullable (o verbo do aluno).
  - `created_at` `DateTime` `server_default=func.now()`.
  - **Unicidade** `(treino_item_id, data)** (UniqueConstraint) — garante uma linha por item por dia (upsert). Head 0028 → **0029**.
- **Serviço (`kairos/execucao/service.py`):**
  - `ValidationError` própria (padrão do domínio) OU reaproveitar de `kairos.treinos.service` — escolher o mais simples e coerente; mensagens pt-BR.
  - `registrar_execucao(treino_item_id, *, feito=None, carga_real=None, reps_real=None, observacao=None, data=None) -> Dict`: `data` default = `datetime.date.today()`. Normaliza `carga_real`/`reps_real`/`observacao` (vazio→None). `feito` vira `bool(feito)`. Verifica que o `TreinoItem` existe (senão `ValidationError("Exercício não encontrado.")`). **Upsert por (treino_item_id, data):** se existe linha do dia, atualiza os campos; senão cria. Loga (regra 8). Retorna o dict da execução.
  - `get_execucao(treino_item_id, data=None) -> Optional[Dict]`: a execução daquele item na data (default hoje), ou None.
  - `list_execucoes(treino_item_id) -> List[Dict]`: histórico, ordenado por `data` desc, `id` desc.
  - `execucoes_do_treino(treino_id, data=None) -> Dict[int, Dict]`: mapa `treino_item_id → execução daquele dia` (default hoje), para a UI (fatia 10) preencher os cards sem N chamadas.
  - `progresso_sessao(treino_id, data=None) -> Dict`: `{"total": n_itens_do_treino, "feitos": n_itens_com_execucao_feito_no_dia}` (default hoje). `total` = itens do treino; `feitos` = itens com linha `feito=True` naquela data.
  - Registrar de módulo: incluir `ExecucaoItem` onde o Alembic/`Base.metadata` enxerga os models (mesmo mecanismo que `registro_treino`/`nivel` usam para serem descobertos).

Casos de borda: `treino_item_id` inexistente → `ValidationError` (nada gravado); registrar duas vezes no mesmo dia → uma linha (segunda atualiza); observação vazia → NULL; `progresso_sessao` de treino sem itens → `{"total": 0, "feitos": 0}` (sem divisão; o percentual é decisão da UI na 10); execução em dia sem registro → `get_execucao` None.

## Pré-condições
- Head 0028 (fatias 01–08 concluídas). Esta fatia adiciona **0029**.
- `TreinoItem` existe; nada da UI aqui (é a fatia 10).

## Arquivos a modificar / criar
- `kairos/execucao/__init__.py` — novo (se o padrão dos módulos tiver).
- `kairos/execucao/models.py` — **novo** (`ExecucaoItem`).
- `kairos/execucao/service.py` — **novo** (registrar/get/list/execucoes_do_treino/progresso).
- `migrations/versions/0029_create_execucoes_item.py` — nova migração.
- (onde os models são importados para o metadata/migração — espelhar `registro_treino`).

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): `ExecucaoItem` + migração 0029 + descoberta do model.
- **serviço** (`servico-writer`): `registrar_execucao`, `get_execucao`, `list_execucoes`, `execucoes_do_treino`, `progresso_sessao`.
- **testes** (`teste-writer`): `tests/test_execucao_servico.py` — registrar cria linha; segundo registro no mesmo dia atualiza (upsert, não duplica); datas diferentes = linhas separadas (histórico via `list_execucoes`); `get_execucao` do dia/None; normalização (vazio→None); `feito` bool; `treino_item` inexistente → ValidationError; `progresso_sessao` conta feitos do dia / total; `execucoes_do_treino` mapeia por item. Novo `tests/test_execucao_item_model.py` (colunas + unique). Atualizar `HEAD_REVISION` 0028→0029 e `test_scaffold`. Suíte completa verde.
