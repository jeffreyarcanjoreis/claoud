# Modelo e migração de Avaliação

## Descrição
A entidade Avaliação do modelo de domínio: pertence ao aluno; campos data, peso, altura, gordura (%), massa magra, massa gorda. Modelo SQLAlchemy + migração Alembic. Nada de derivados (Δ, IMC) no banco — são calculados depois.

## Depende de
nenhuma

## Especificação funcional
- Existe a tabela `avaliacoes` com uma linha por avaliação de um aluno.
- Colunas: `id` (PK), `aluno_id` (FK → alunos.id, NOT NULL, indexado para listar por aluno), `data` (Date, NOT NULL), `peso`, `altura`, `gordura_pct`, `massa_magra`, `massa_gorda` (todos numéricos e nullable), `created_at` (DateTime NOT NULL, default agora).
- Nenhum derivado no banco: não há coluna de Δ nem de IMC (são calculados na hora, regra de ouro do domínio).
- Tipos portáveis apenas (regra 4): `ForeignKey`, `Numeric`, `Date`, `DateTime`. As métricas usam `Numeric` (não float) para precisão de medida; campo sem dado é NULL (regra 6).
- Ao iniciar a app num banco novo, a migração cria a tabela até head (`0003`); num banco existente, aplica-se por cima do `0002` com o backup automático já existente.

## Pré-condições
- Fatia 2 concluída; migração head atual é `0002`; `migrations/env.py` importa os modelos para o metadata; runner de migração com backup já existe. 123 testes verdes.

## Arquivos a criar
- `kairos/avaliacoes/__init__.py` — docstring de uma linha (módulo de domínio "avaliacoes").
- `kairos/avaliacoes/models.py` — modelo `Avaliacao` (SQLAlchemy 2.x, estilo `Mapped`/`mapped_column`, herda de `kairos.db.Base`), tabela `avaliacoes`, com as colunas acima. `aluno_id`: `mapped_column(ForeignKey("alunos.id"), nullable=False, index=True)`. Métricas: `Numeric` com precisão razoável (ex.: peso/massas `Numeric(5,2)`, altura `Numeric(5,2)` em cm, gordura `Numeric(4,1)`), nullable. `data` Date NOT NULL. `created_at` DateTime server_default `func.now()`. `__repr__` curto.
- `migrations/versions/0003_create_avaliacoes.py` — revision "0003", down_revision "0002"; cria a tabela `avaliacoes` com os mesmos tipos portáveis (`sa.Numeric`, `sa.Date`, `sa.DateTime`, `sa.ForeignKey("alunos.id")`), índice em `aluno_id`; downgrade dropa a tabela.
- `tests/test_avaliacao_model.py` — com KAIROS_DATA_DIR temp: (a) após startup, a tabela `avaliacoes` existe e a revisão está em `0003`; (b) inserir uma avaliação ligada a um aluno e ler de volta funciona (colunas presentes, métricas aceitam decimais e NULL).

## Arquivos a modificar
- `migrations/env.py` — acrescentar `import kairos.avaliacoes.models  # noqa: E402,F401` junto do import de `kairos.alunos.models`, para o metadata conhecer a tabela.
- `tests/test_scaffold.py` — atualizar a constante de revisão head (hoje `"0002"`) para `"0003"` (a suíte assume o head atual). Se o teste de "migração pendente" rebaixa/estampa revisões, ajustar para o novo head mantendo o significado.

## Camadas envolvidas
banco/migração (modelo + Alembic), teste

## Status
concluída
