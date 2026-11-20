# Arco da sessão — proporções vivas (coach ajusta os minutos por fase)

## Descrição
O coach ajusta os minutos de cada uma das 5 fases ao momento (ansioso → mais preparação/aquecimento; radiante → mais skill/ápice), mantendo a soma = duração. "Estrutura fixa, proporções vivas." Comportamento [F1] 5.

## Depende de
13–15 (arco: duração + `arco_da_sessao` + componente visual)

## Status
planejada

## Especificação funcional
O arco deixa de ser só derivado: o coach pode **sobrescrever** os minutos de cada fase. Com override → o arco usa os minutos salvos; sem override → a tabela canônica (regra 6: nunca minutos inventados; o default é derivado). A estrutura é fixa (as 5 fases sempre presentes, cada uma ≥ 1 min) e a soma dos 5 deve ser exatamente a duração. O lado do aluno já reflete automaticamente (lê `arco_da_sessao`).

- **Dados (migração 0033):** adicionar a `treinos` cinco colunas `Integer` nullable, uma por fase (ordem de `FASE_OPCOES`): `min_preparacao`, `min_aquecimento`, `min_skill`, `min_apice`, `min_volta_a_calma`. Todas NULL = "proporções no padrão"; todas preenchidas = override vivo. Model `Treino` ganha as 5. Head 0032 → **0033**.
- **Serviço (`kairos/treinos/service.py`):**
  - `MIN_FASE_COLS = {"preparacao":"min_preparacao", ...}` (mapa fase→coluna), na ordem de `FASE_OPCOES`.
  - `set_proporcoes(treino_id, minutos: Dict[str, Any]) -> Optional[Dict]`: get-or-None. Validar (ANTES de gravar): o treino tem `duracao_min` (senão `ValidationError("Defina a duração antes de ajustar as proporções.")`); as 5 fases presentes em `minutos`; cada valor int ≥ 1 (senão `ValidationError("Cada fase precisa de ao menos 1 minuto.")` / "Minutos inválidos."); soma == `duracao_min` (senão `ValidationError(f"As proporções devem somar {duracao} min (somaram {total}).")`). Persistir as 5 colunas; loga; retorna o treino (dict). Aceitar valores string numérica ("12") ou int.
  - `reset_proporcoes(treino_id) -> Optional[Dict]`: zera as 5 colunas (volta ao padrão/canônico); loga; retorna o treino.
  - `set_duracao`: ao **mudar** a duração (parsed != duracao_min atual) ou limpar, **resetar as 5 colunas** (as proporções antigas violariam a nova soma). Se a duração for a mesma, não mexer nas proporções.
  - `arco_da_sessao`: se as 5 colunas de override estão preenchidas, usar esses minutos; senão, a tabela canônica. Cada fase do retorno ganha `"ajustado": bool` (True quando o minuto efetivo difere do canônico daquela duração). Opcional: expor no treino-dict `arco_ajustado` (qualquer override setado).
  - `_treino_to_dict`: incluir as 5 colunas (`min_preparacao` etc.) — útil para pré-preencher o form.

- **Rota (coach, `kairos/treinos/routes.py`):**
  - `POST /alunos/{aluno_id}/treino/{treino_id}/proporcoes` (form: `min_preparacao`, `min_aquecimento`, `min_skill`, `min_apice`, `min_volta_a_calma`): gate de coach (padrão de `set_duracao_route`); montar o dict `minutos`; `set_proporcoes(...)`; em `ValidationError` **reexibir a planilha com a mensagem** (mesmo mecanismo de erro já usado — `_arco_context` + erro 400), para o coach ver o que faltou somar; sucesso → 303.
  - `POST /alunos/{aluno_id}/treino/{treino_id}/proporcoes/resetar`: gate; `reset_proporcoes`; 303.
  - O `arco` já vem de `arco_da_sessao` (agora com `ajustado`); passar também os valores atuais por fase para pré-preencher o form (via o dict do treino).

- **Template (`kairos/templates/treinos/aluno_detalhe.html`):** quando há `arco` (duração definida), um `<details>` "Ajustar proporções (ao momento)" com um form: um `<input type="number" min="1">` por fase (rótulo = fase; pré-preenchido com os minutos atuais do arco), uma dica "devem somar {{ duracao_min }} min", botão "Salvar proporções" e, quando houver override, um botão "voltar ao padrão" (POST resetar). No componente de arco, marcar visualmente as fases `ajustado` (ex. um ponto/again discreto "ajustado"). Copy no tom do método (ajustar ao momento, não corrigir).

- **CSS:** inputs de proporção compactos (linha), marca discreta de fase ajustada. Só tokens existentes.

Casos de borda: soma ≠ duração → erro reexibido, nada gravado; alguma fase < 1 ou vazia/não-numérica → erro; sem duração → `set_proporcoes` erro ("defina a duração antes"); trocar a duração depois de ajustar → reseta ao padrão da nova duração; treino de outro aluno → 404; aluno continua só lendo o arco (reflete o ajuste).

## Pré-condições
- Fatias 13–15 concluídas. Head 0032. Esta fatia adiciona **0033**.

## Arquivos a modificar / criar
- `migrations/versions/0033_add_proporcoes_to_treinos.py` — nova migração.
- `kairos/treinos/models.py` — 5 colunas de minutos por fase em `Treino`.
- `kairos/treinos/service.py` — `MIN_FASE_COLS`, `set_proporcoes`, `reset_proporcoes`, `set_duracao` (reset ao mudar), `arco_da_sessao` (override + `ajustado`), `_treino_to_dict`.
- `kairos/treinos/routes.py` — rotas proporções + resetar; pré-preencher o form.
- `kairos/templates/treinos/aluno_detalhe.html` — form de ajuste + marca de ajustado.
- `kairos/static/css/components.css` — inputs + marca.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): migração 0033 + 5 colunas.
- **serviço** (`servico-writer`): `set_proporcoes`, `reset_proporcoes`, `set_duracao` reset, `arco_da_sessao` override+ajustado, dict.
- **aplicação** (`aplicacao-writer`): rotas proporções/resetar + pré-preencher.
- **frontend** (`frontend-writer`): form de ajuste + marca de ajustado + CSS.
- **testes** (`teste-writer`): `tests/test_treino_proporcoes.py` — `set_proporcoes` grava e `arco_da_sessao` reflete (com `ajustado`); soma errada/fase<1/sem duração → ValidationError (nada gravado); `reset_proporcoes` volta ao canônico; `set_duracao` reseta ao mudar a duração e preserva quando igual; rota grava/reseta, erro reexibe com a mensagem de soma, 404 de outro aluno; o aluno vê o arco ajustado. Atualizar `HEAD_REVISION` 0032→0033 + `test_scaffold` + `test_treino_model` (5 colunas novas). Suíte completa verde.
