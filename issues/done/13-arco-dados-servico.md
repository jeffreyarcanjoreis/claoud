# Arco da sessão — dados + serviço

## Descrição
Dar a um treino uma duração de sessão (30/45/60 min) e derivar os minutos de cada uma das 5 fases pela tabela canônica do método. Base de dados + serviço. Comportamentos [F1] 1 e 2.

## Depende de
nenhuma (usa as fases já existentes)

## Status
concluída

## Especificação funcional
Só dados + serviço; a UI é 14 (coach) e 15 (aluno). Regra 6: sem duração = NULL = "sem arco". Os minutos são **derivados** da tabela canônica (nunca digitados/inventados).

- **Dados (migração 0032):** adicionar a `treinos` a coluna `duracao_min` (`Integer`, nullable). Model `Treino` ganha `duracao_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)`. `_treino_to_dict` passa a incluir `"duracao_min"`. Head 0031 → **0032**.
- **Serviço (`kairos/treinos/service.py`):**
  - `DURACAO_OPCOES = (30, 45, 60)`.
  - `PROPORCOES_FASE` — a tabela canônica (minutos por fase por duração), na ordem de `FASE_OPCOES`:
    - 30: preparacao 3, aquecimento 5, skill 7, apice 10, volta_a_calma 5
    - 45: preparacao 4, aquecimento 7, skill 11, apice 16, volta_a_calma 7
    - 60: preparacao 5, aquecimento 9, skill 15, apice 22, volta_a_calma 9
  - `set_duracao(treino_id, duracao) -> Optional[Dict]`: normaliza `duracao` (vazio/None → limpa = NULL "sem arco"); senão deve ser int em `DURACAO_OPCOES` (senão `ValidationError("Duração inválida.")`). Aceita string ("45") ou int. Get-or-None; persiste `duracao_min`; loga; retorna o treino (dict).
  - `arco_da_sessao(treino_id) -> Optional[List[Dict]]`: lê o treino; se `duracao_min` é None → retorna None ("sem arco"). Senão retorna a lista das 5 fases na ordem canônica, cada uma: `{"fase", "fase_label" (FASE_LABELS), "fase_pergunta" (FASE_PERGUNTAS), "minutos" (de PROPORCOES_FASE[duracao][fase])}`. Read-only, sem log.
  - `get_treino` e `get_treino_detail` já usam `_treino_to_dict`, então passam a expor `duracao_min` automaticamente (confirmar).

Casos de borda: duração fora de (30,45,60) → ValidationError (nada gravado); limpar (vazio) → NULL; `arco_da_sessao` de treino sem duração → None; treino inexistente → `set_duracao` None / `arco_da_sessao` None; a soma dos minutos de cada duração bate com a duração (30→3+5+7+10+5=30; 45→4+7+11+16+7=45; 60→5+9+15+22+9=60) — garantir na tabela.

## Pré-condições
- Head 0031 (trilha Treino concluída). Esta fatia adiciona **0032**.
- `FASE_OPCOES`/`FASE_LABELS`/`FASE_PERGUNTAS` já existem no serviço.

## Arquivos a modificar / criar
- `migrations/versions/0032_add_duracao_to_treinos.py` — nova migração.
- `kairos/treinos/models.py` — coluna `duracao_min` em `Treino`.
- `kairos/treinos/service.py` — `DURACAO_OPCOES`, `PROPORCOES_FASE`, `set_duracao`, `arco_da_sessao`; `duracao_min` em `_treino_to_dict`.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): migração 0032 + coluna no model.
- **serviço** (`servico-writer`): opções/tabela, `set_duracao`, `arco_da_sessao`, `duracao_min` no dict.
- **testes** (`teste-writer`): `tests/test_treino_arco.py` — `set_duracao` grava 30/45/60 e limpa; inválida → ValidationError; `arco_da_sessao` retorna as 5 fases com os minutos certos por duração e None sem duração; soma dos minutos = duração; `get_treino`/`get_treino_detail` expõem `duracao_min`. Atualizar `HEAD_REVISION` 0031→0032 + `test_scaffold` + `test_treino_model` (coluna nova). Suíte completa verde.
