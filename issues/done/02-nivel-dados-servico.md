# Nível autorreconhecido — dados + serviço

## Descrição
A base do nível autodeterminado: guardar cada autorreconhecimento de nível de um aluno (nível I–IV, data, nota opcional) como histórico, expor o nível atual (o reconhecimento mais recente) e a lista do histórico, e registrar um novo reconhecimento validando o nível contra o conjunto I–IV. Nota vazia fica NULL. O nível nunca é definido por ninguém além do próprio aluno (a rota do aluno é quem chama).

## Depende de
nenhuma

## Status
concluída

## Especificação funcional
Domínio novo `nivel` (autorreconhecimento de nível), espelhando o módulo `registro_treino` (modelo + serviço, sem rotas nesta fatia). Cada reconhecimento é um registro imutável; **o atual é o mais recente** e os anteriores ficam no histórico (mostra evolução; regra 6: nada é sobrescrito nem inventado).

- **Vocabulário (fonte única, no serviço — o lado do aluno/coach importa daqui):**
  - `NIVEL_OPCOES = ("fundacao", "construcao", "dominio", "maestria")` (ordem = progressão I→IV).
  - `NIVEL_LABELS = {fundacao: "I · Fundação", construcao: "II · Construção", dominio: "III · Domínio", maestria: "IV · Maestria"}`.
  - `NIVEL_DESCRICOES` (1ª pessoa, pt-BR): fundacao "Aprendo a sentir, domino o simples." · construcao "Amplio a capacidade, com domínio crescente." · dominio "Tenho autonomia, refino, encaro desafios reais." · maestria "Alta capacidade e autorregulação — quase me conduzo."
- **`reconhecer(aluno_id, *, nivel, nota=None)`:**
  - valida `nivel` ∈ `NIVEL_OPCOES`; senão `ValidationError("Nível inválido.")` (nada gravado).
  - normaliza `nota` (vazio/whitespace → `None`, regra 6).
  - cria **sempre um novo** `ReconhecimentoNivel` (nunca upsert — histórico); `flush`/`refresh`; **loga** a escrita (regra 8); retorna o dict.
  - a existência de `aluno_id` **não** é checada aqui (responsabilidade da rota — issue 03).
- **`nivel_atual(aluno_id)`** → dict do reconhecimento mais recente (created_at desc, id desc como desempate), ou `None` quando o aluno ainda não se reconheceu. Read-only, sem log.
- **`list_reconhecimentos(aluno_id)`** → lista de dicts do aluno, mais recente primeiro (created_at desc, id desc). Read-only, sem log.
- **dict (`_to_dict`)**: `id`, `aluno_id`, `nivel`, `nivel_label`, `nivel_descricao`, `nota`, `created_at`. Primitivos extraídos com a sessão aberta (evita DetachedInstanceError, como no `registro_treino`).

Casos de borda: nível fora do conjunto → recusado sem gravar; nota vazia → NULL; dois reconhecimentos do mesmo nível em momentos diferentes são dois registros (histórico); aluno sem reconhecimento → `nivel_atual` None e `list_reconhecimentos` [].

## Pré-condições
- Domínio `alunos` existe (FK `aluno_id` → `alunos.id`). HEAD de migração: **0023**.

## Arquivos a criar
- `kairos/nivel/__init__.py` — docstring do domínio ("autorreconhecimento de nível do aluno").
- `kairos/nivel/models.py` — `ReconhecimentoNivel(Base)`, tabela `reconhecimentos_nivel`: `id` (PK autoincrement), `aluno_id` (FK `alunos.id`, not null, index), `nivel` (String(20), not null — validado no serviço), `nota` (Text, nullable), `created_at` (DateTime, not null, server_default `func.now()`). **Sem** unique constraint (vários reconhecimentos por aluno — histórico). Tipos portáveis; `__repr__` no estilo do `registro_treino`.
- `kairos/nivel/service.py` — as constantes acima, `ValidationError`, helpers (`_normalize`, `_to_dict`), `reconhecer`, `nivel_atual`, `list_reconhecimentos`. Usa `session_scope` e `logging` como `kairos/registro_treino/service.py`.
- `migrations/versions/0024_create_reconhecimentos_nivel.py` — cria a tabela espelhando o modelo (FK para `alunos.id`, index em `aluno_id`, sem unique). `revision = "0024"`, `down_revision = "0023"`. `downgrade()` dropa índice e tabela.

## Arquivos a modificar
- Nenhum. (Sem rota/inclusão em `main.py` nesta fatia — o router do aluno vem na issue 03; o coach lê na issue 04.)

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): `ReconhecimentoNivel` + migração 0024.
- **serviço** (`servico-writer`): `nivel/service.py` (vocabulário, `reconhecer`, `nivel_atual`, `list_reconhecimentos`).
- **testes** (`teste-writer`): `tests/test_nivel.py` cobrindo `reconhecer` (válido, inválido não grava, nota vazia→None, histórico com vários), `nivel_atual` (mais recente / None), `list_reconhecimentos` (ordem desc / vazio); bump de `HEAD_REVISION` 0023→0024 nos testes que fixam a head. Suíte anterior verde.
