# Campo de foto no aluno

## Descrição
O Aluno ganha um campo `foto` (nome do ficheiro guardado, nullable) no modelo, com a migração Alembic correspondente. Sem valor = sem foto (regra 6).

## Depende de
nenhuma

## Especificação funcional
- A tabela `alunos` ganha a coluna `foto` (texto, nullable) — guarda o nome do ficheiro da foto; NULL = sem foto (regra 6).
- `get_aluno`/`create_aluno`/`update_aluno` passam a incluir a chave `foto` no dict devolvido (para as próximas issues poderem mostrar/servir).
- Nenhum comportamento existente muda (foto começa NULL; o form de aluno não mexe nela — o upload é fatia à parte).
- Ao iniciar num banco novo, a migração cria a coluna até head (`0005`); num existente, aplica por cima do `0004` com o backup automático.

## Pré-condições
- Fatia 5 concluída; migração head atual é `0004`; 197 testes verdes. `migrations/env.py` já importa `kairos.alunos.models`.

## Arquivos a criar
- `migrations/versions/0005_add_foto_to_alunos.py` — revision "0005", down_revision "0004". `upgrade`: `op.add_column("alunos", sa.Column("foto", sa.String(255), nullable=True))` (SQLite aceita ADD COLUMN direto). `downgrade`: apagar a coluna de forma portável a SQLite — usar `op.batch_alter_table("alunos") as batch: batch.drop_column("foto")` (SQLite não faz DROP COLUMN simples em versões antigas; o batch garante).
- `tests/test_foto_modelo.py` — com KAIROS_DATA_DIR temp: (a) após startup, a tabela `alunos` tem a coluna `foto` e a revisão é `0005`; (b) criar um aluno e confirmar que `foto` vem `None` por padrão (via get_aluno ou SQL); (c) definir `foto` numa linha via SQL/ORM e ler de volta funciona.

## Arquivos a modificar
- `kairos/alunos/models.py` — acrescentar `foto: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)` à classe `Aluno`.
- `kairos/alunos/service.py` — em `_to_dict`, acrescentar `"foto": aluno.foto` (para o campo ficar disponível em get/create/update). Não mudar validação nem `_clean_fields` (a foto não vem do form de texto).
- `tests/test_scaffold.py`, `tests/test_avaliacao_model.py`, `tests/test_perimetria_model.py` — atualizar `HEAD_REVISION` de `"0004"` para `"0005"` (os três têm a constante). No `test_scaffold`, se o teste de migração pendente estampa/rebaixa e dropa a tabela da última migração, ajustar: agora a última migração é um ADD COLUMN (0005), não um CREATE TABLE — para a simulação de "pendente" continuar a fazer sentido, estampar a revisão anterior `"0004"` e, em vez de dropar uma tabela, deixar o upgrade re-aplicar (ou dropar a coluna `foto` via batch). Manter o significado (backup ANTES do upgrade).

## Camadas envolvidas
banco/migração (modelo + Alembic), serviço (expor `foto` no dict), teste

## Status
concluída
