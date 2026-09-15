# Modelo e migração de SessaoAgendada

## Descrição
A entidade SessaoAgendada do modelo de domínio: pertence a um aluno (FK); data, hora, tipo (individual/grupo), e duração (min) e observação opcionais. Modelo SQLAlchemy + migração Alembic. Nenhum derivado no banco.

## Depende de
nenhuma

## Especificação funcional
- Existe a tabela `sessoes_agendadas`: uma linha por sessão agendada de um aluno.
- Colunas: `id` (PK), `aluno_id` (FK → alunos.id, NOT NULL, indexado), `data` (Date, NOT NULL), `hora` (Time, NOT NULL), `duracao_min` (Integer, nullable), `tipo` (texto, NOT NULL — "individual"/"grupo"), `observacao` (Text, nullable), `created_at` (DateTime NOT NULL, default agora).
- Tipos portáveis apenas (regra 4). Nenhum derivado no banco.
- Ao iniciar num banco novo, a migração cria a tabela até head (`0006`); num existente, aplica por cima do `0005` com o backup automático.

## Pré-condições
- Fatia 6 concluída; migração head atual é `0005`; 231 testes verdes. `migrations/env.py` importa os modelos por módulo (ainda não importa o módulo agenda).

## Arquivos a criar
- `kairos/agenda/__init__.py` — docstring de uma linha (módulo de domínio "agenda").
- `kairos/agenda/models.py` — modelo `SessaoAgendada` (SQLAlchemy 2.x, Mapped/mapped_column, herda de `kairos.db.Base`), tabela `sessoes_agendadas`, com as colunas acima. `aluno_id`: `mapped_column(ForeignKey("alunos.id"), nullable=False, index=True)`. `data` `Date` NOT NULL; `hora` `Time` NOT NULL; `duracao_min` `Integer` nullable; `tipo` `String(20)` NOT NULL; `observacao` `Text` nullable; `created_at` `DateTime` server_default `func.now()`. `__repr__` curto (id, aluno_id, data, hora).
- `migrations/versions/0006_create_sessoes_agendadas.py` — revision "0006", down_revision "0005"; `op.create_table("sessoes_agendadas", ...)` com os mesmos tipos portáveis (`sa.Integer`, `sa.Date`, `sa.Time`, `sa.String(20)`, `sa.Text`, `sa.DateTime`, `sa.ForeignKey("alunos.id")`), índice em `aluno_id`; downgrade dropa índice e tabela.
- `tests/test_sessao_agendada_model.py` — com KAIROS_DATA_DIR temp: (a) após startup, a tabela `sessoes_agendadas` existe e a revisão é `0006`; (b) inserir uma sessão ligada a um aluno (com data/hora/tipo, e duracao_min/observacao NULL) e ler de volta funciona; (c) a tabela não tem colunas de derivados.

## Arquivos a modificar
- `migrations/env.py` — acrescentar `import kairos.agenda.models  # noqa: E402,F401` junto dos outros imports de modelos.
- `tests/test_scaffold.py`, `tests/test_avaliacao_model.py`, `tests/test_perimetria_model.py`, `tests/test_foto_modelo.py` — atualizar `HEAD_REVISION`/asserção de revisão de `"0005"` para `"0006"` (os quatro assumem o head atual). No `test_scaffold`, o teste de migração pendente estampa a revisão anterior e dropa a tabela da última migração: passar a estampar `"0005"` e dropar a tabela `sessoes_agendadas` (criada por 0006). Manter o significado (backup ANTES do upgrade).

## Camadas envolvidas
banco/migração (modelo + Alembic), teste

## Status
concluída
