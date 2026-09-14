# Níveis do exercício — aluno escolhe "meu lugar hoje"

## Descrição
O aluno escolhe, entre base/regressão/progressão, a variação em que se reconhece hoje (autodeterminado; regras 11–14). A escolha é dele, revisável, e fica visível para ele e para o coach. Comportamento [F+] 17.

## Depende de
07 (o coach precisa ter descrito as variações)

## Status
concluída

## Especificação funcional
A escolha é **por item do treino** (`TreinoItem`): uma única escolha corrente, revisável (trocar apenas sobrescreve; nada de histórico nesta fatia). Fidelidade ao método (regras 11–14): quem escolhe é o **aluno**, sobre si mesmo, em primeira pessoa ("onde eu me reconheço hoje"); o coach não gradua nem trava — apenas **vê** a escolha. Guardar o dado nunca inventado (regra 6): sem escolha = NULL = "ainda não me reconheci".

- **Dados (migração 0028):** adicionar a `treino_itens` a coluna `variacao_escolhida` (`String(20)`, nullable). Valores válidos: `"base"`, `"regressao"`, `"progressao"` ou NULL. Model `TreinoItem` ganha `variacao_escolhida: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)`. Head 0027 → **0028**.
- **Serviço (`kairos/treinos/service.py`):**
  - `VARIACAO_OPCOES = ("base", "regressao", "progressao")` e `VARIACAO_LABELS = {"base": "Base", "regressao": "Regressão", "progressao": "Progressão"}`.
  - `escolher_variacao(item_id, escolha) -> Optional[Dict]`: `escolha` normalizada; vazio/None → limpa (NULL, "revisar/ainda não"); senão deve estar em `VARIACAO_OPCOES` (senão `ValidationError("Variação inválida.")`). Get-or-None. Persiste `variacao_escolhida`; loga; retorna o item (dict). Não exige que a variação escolhida tenha descrição — o aluno se reconhece mesmo assim; a UI é que oferece as descritas.
  - `get_treino_detail`: cada item passa a expor `variacao_escolhida` e `variacao_escolhida_label` (via `VARIACAO_LABELS`).
- **Rotas:**
  - **Aluno** (`kairos/area_aluno/routes.py`): `POST /aluno/treinos/{treino_id}/itens/{item_id}/variacao` (form `escolha`). Padrão de gate do aluno já usado no arquivo: `aluno_id = _aluno_id_da_sessao(request)`; `get_treino(treino_id)`; 404 (`_nao_encontrado`) se o treino não existe ou não é do aluno; confirmar que o item pertence ao treino (via `get_item`/`get_treino_detail`) senão 404. `escolher_variacao(item_id, escolha)`; em `ValidationError` tratar como no-op (redirect, sem 500); 303 de volta para `/aluno/treinos/{treino_id}`.
  - **Coach** (leitura): a planilha do coach já usa `get_treino_detail`; nenhuma rota nova — só exibição (a escolha do aluno aparece read-only no card do coach).
- **Templates:**
  - `kairos/templates/area_aluno/treino_detalhe.html`: no card, abaixo do bloco "Variações" (fatia 07), um seletor em **primeira pessoa** — título tipo "Onde eu me reconheço hoje?" — com uma opção por variação **descrita** pelo coach (só as preenchidas: base/regressão/progressão) mais a opção de **rever** (limpar). Cada opção é um `<button>`/form POST (`escolha=base|regressao|progressao` ou vazio para limpar) para a rota nova. A opção atualmente escolhida aparece destacada/marcada. Copy acolhedora, sem juízo de valor (nada de "nível fácil/difícil"; é reconhecimento, não nota). Se o coach não descreveu nenhuma variação, não mostrar seletor.
  - `kairos/templates/treinos/aluno_detalhe.html` (coach): quando `i.variacao_escolhida` existir, uma linha read-only discreta tipo "O aluno se reconheceu em: {{ label }}" (espelho, não avaliação — regra 13). Sem escolha → nada (regra 6).
- **CSS:** estilo do seletor "meu lugar hoje" (opções em botões/chips; a escolhida destacada com o acento do tema). Coerente com a estética.

Casos de borda: treino/item de outro aluno → 404; `escolha` adulterada (fora das opções) → no-op (303, nada muda); escolher e depois rever (limpar) → volta a NULL; aluno escolhe uma variação e o coach depois apaga a descrição dela → a escolha permanece e o card mostra o rótulo (degrada sem quebrar).

## Pré-condições
- Head 0027 (fatias 01–07 concluídas). Esta fatia adiciona **0028**.
- Variações descritas pelo coach (fatia 07) já estão em `get_treino_detail`.

## Arquivos a modificar / criar
- `migrations/versions/0028_add_variacao_escolhida_to_treino_itens.py` — nova migração.
- `kairos/treinos/models.py` — coluna `variacao_escolhida` em `TreinoItem`.
- `kairos/treinos/service.py` — `VARIACAO_OPCOES`/`VARIACAO_LABELS`, `escolher_variacao`, `variacao_escolhida`(+label) no detail.
- `kairos/area_aluno/routes.py` — rota POST de escolha (gate do aluno).
- `kairos/templates/area_aluno/treino_detalhe.html` — seletor "meu lugar hoje".
- `kairos/templates/treinos/aluno_detalhe.html` — leitura da escolha (coach).
- `kairos/static/css/components.css` — estilo do seletor.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): migração 0028 + coluna no model.
- **serviço** (`servico-writer`): opções/labels, `escolher_variacao`, campos no detail.
- **aplicação** (`aplicacao-writer`): rota POST do aluno (gate + 404 + no-op em escolha inválida).
- **frontend** (`frontend-writer`): seletor em primeira pessoa (aluno) + leitura da escolha (coach) + CSS.
- **testes** (`teste-writer`): `tests/test_treino_variacao_escolha.py` — `escolher_variacao` grava/limpa/rejeita inválida; `get_treino_detail` expõe valor+label; rota do aluno grava e reflete; treino/item de outro aluno → 404; escolha adulterada → no-op; seletor só aparece quando há variação descrita; escolha atual destacada; card do coach mostra a escolha read-only. Atualizar `HEAD_REVISION` 0027→0028 e o teste de colunas de `treino_itens` (+1). Suíte completa verde.
