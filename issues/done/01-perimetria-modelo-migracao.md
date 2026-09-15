# Modelo e migração de Perimetria

## Descrição
A entidade Perimetria (medida) do modelo de domínio: pertence a uma Avaliação (FK), com segmento (texto) e valor (Numeric, cm). Tabela filha — uma linha por segmento medido. Modelo SQLAlchemy + migração Alembic.

## Depende de
nenhuma

## Especificação funcional
- Existe a tabela `perimetrias`: uma linha por segmento medido de uma avaliação.
- Colunas: `id` (PK), `avaliacao_id` (FK → avaliacoes.id, NOT NULL, indexado), `segmento` (texto, NOT NULL), `valor` (Numeric, cm, NOT NULL — uma linha só existe se tem valor).
- Restrição de unicidade em `(avaliacao_id, segmento)`: no máximo uma medida por segmento por avaliação.
- Tipos portáveis apenas (regra 4). Nenhum derivado no banco (o Δ é calculado depois).
- Ao iniciar num banco novo, a migração cria a tabela até head (`0004`); num existente, aplica por cima do `0003` com o backup automático.

## Pré-condições
- Fatia 4 concluída; migração head atual é `0003`; `migrations/env.py` já importa `kairos.avaliacoes.models` (a nova classe, no mesmo módulo, é registada automaticamente). 176 testes verdes.

## Arquivos a criar
- `migrations/versions/0004_create_perimetrias.py` — revision "0004", down_revision "0003"; `op.create_table("perimetrias", ...)` com `id`, `avaliacao_id` (`sa.ForeignKey("avaliacoes.id")`, NOT NULL), `segmento` (`sa.String(50)`, NOT NULL), `valor` (`sa.Numeric(5,2)`, NOT NULL); `op.create_index` em `avaliacao_id`; `op.create_unique_constraint` (ou `UniqueConstraint` na criação) em `(avaliacao_id, segmento)`. Downgrade dropa a tabela.
- `tests/test_perimetria_model.py` — com KAIROS_DATA_DIR temp: (a) após startup, a tabela `perimetrias` existe e a revisão é `0004`; (b) inserir uma linha de perimetria ligada a uma avaliação de um aluno funciona (colunas presentes, valor decimal volta correto); (c) a tabela não tem colunas de derivados.

## Arquivos a modificar
- `kairos/avaliacoes/models.py` — acrescentar a classe `Perimetria` (SQLAlchemy 2.x, Mapped/mapped_column, herda de `kairos.db.Base`), tabela `perimetrias`, com as colunas acima e a `UniqueConstraint("avaliacao_id", "segmento")` no `__table_args__`. `valor` Numeric(5,2) NOT NULL. `__repr__` curto (id, avaliacao_id, segmento).
- `tests/test_scaffold.py` — atualizar `HEAD_REVISION` de `"0003"` para `"0004"`; se o teste de migração pendente estampa/rebaixa revisões, ajustar para o novo head mantendo o significado (o segmento a dropar na simulação passa a ser `perimetrias`, criado por 0004).

## Camadas envolvidas
banco/migração (modelo + Alembic), teste

## Status
concluída
