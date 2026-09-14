# Níveis do exercício — coach descreve (base/regressão/progressão)

## Descrição
Ao montar o treino, o coach descreve as três variações de um exercício: base, regressão e progressão. Elas aparecem no card do exercício (coach e aluno). Comportamento [F+] 16.

## Depende de
nenhuma

## Status
concluída

## Especificação funcional
As três variações são **por item do treino** (`TreinoItem`) — o coach as descreve no contexto daquela planilha, não na biblioteca. São textos livres, nulos por padrão ("sem registro", regra 6): um exercício pode não ter variações descritas. O coach as edita **junto da edição do item** (mesmo formulário da fatia 04), mantendo um só lugar para configurar o exercício. Fidelidade ao método (regras 11–14): o coach **descreve/oferece caminhos** (base, um passo atrás, um passo adiante) — não gradua nem obriga.

- **Dados (migração 0027):** adicionar a `treino_itens` três colunas `Text` nullable: `variacao_base`, `variacao_regressao`, `variacao_progressao`. Model `TreinoItem` ganha os três `Mapped[Optional[str]] = mapped_column(Text, nullable=True)`. Head 0026 → **0027**.
- **Serviço (`kairos/treinos/service.py`):**
  - `update_item(...)` passa a aceitar e persistir `variacao_base`, `variacao_regressao`, `variacao_progressao` (raw strings → `_normalize` → None quando vazio). Mesma semântica dos outros campos: validação antes de tocar a sessão; retorna o dict do item incluindo as três variações.
  - `get_treino_detail`: cada item do dict passa a expor `variacao_base`, `variacao_regressao`, `variacao_progressao`.
  - (`add_item_to_treino` NÃO muda — variações são descritas na edição, mantendo o form de adicionar enxuto.)
- **Rotas (`kairos/treinos/routes.py`):**
  - `edit_item_form` (GET): o contexto passa a incluir os três valores atuais do item, para pré-preencher.
  - `update_item_route` (POST): recebe os três novos campos de form (`variacao_base`, `variacao_regressao`, `variacao_progressao`) e os repassa a `update_item`.
  - `_to_item_display` (se usado) inclui as três variações.
- **Templates:**
  - `kairos/templates/treinos/item_editar.html`: três `<textarea>` rotulados **Base**, **Regressão** e **Progressão** (copy do coach: descrever o caminho de cada uma), pré-preenchidos. Uma linha de ajuda curta reforçando o tom (oferecer caminhos, não graduar).
  - `kairos/templates/treinos/aluno_detalhe.html` (planilha do coach): no card do exercício, quando houver ao menos uma variação, um bloco discreto "Variações" listando as que existirem (Base/Regressão/Progressão), cada uma só aparece se preenchida (regra 6).
  - `kairos/templates/area_aluno/treino_detalhe.html` (planilha do aluno): mesmo bloco read-only de variações no card (o aluno lê os caminhos; escolher "meu lugar hoje" é a fatia 08).
- **CSS:** bloco de variações discreto (usar tokens; rótulo pequeno por variação).

Casos de borda: item sem nenhuma variação → nenhum bloco no card (nada de placeholder falso); item inexistente na edição → 404 (padrão da fatia 04); variação só num dos três campos → só ela aparece.

## Pré-condições
- Head 0026 (fatias 01–06 concluídas). Esta fatia adiciona **0027**.
- Form/rota de editar item (fatia 04) existem e serão estendidos.

## Arquivos a modificar / criar
- `migrations/versions/0027_add_variacoes_to_treino_itens.py` — nova migração.
- `kairos/treinos/models.py` — três colunas em `TreinoItem`.
- `kairos/treinos/service.py` — `update_item` + `get_treino_detail`.
- `kairos/treinos/routes.py` — `edit_item_form` + `update_item_route` (+ `_to_item_display`).
- `kairos/templates/treinos/item_editar.html` — três textareas.
- `kairos/templates/treinos/aluno_detalhe.html` — bloco de variações (coach).
- `kairos/templates/area_aluno/treino_detalhe.html` — bloco de variações (aluno, read-only).
- `kairos/static/css/components.css` — estilo do bloco de variações.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): migração 0027 + colunas no model.
- **serviço** (`servico-writer`): `update_item` + `get_treino_detail`.
- **aplicação** (`aplicacao-writer`): `edit_item_form` + `update_item_route`.
- **frontend** (`frontend-writer`): textareas na edição + bloco de variações nas duas planilhas + CSS.
- **testes** (`teste-writer`): `tests/test_treino_variacoes.py` — `update_item` grava/limpa as três variações; `get_treino_detail` as expõe; campo vazio → None; rota GET de edição pré-preenche; POST grava; card mostra só as preenchidas. Atualizar `HEAD_REVISION` 0026→0027 e o teste de colunas de `treino_itens` (+3 colunas). Atualizar `test_treino_editar_item.py` se assere o shape do update. Suíte completa verde.
