# Estrutura do treino — planilha do coach (montar em fases)

## Descrição
Na planilha do treino do coach (`/alunos/{id}/treino/{treino_id}`): ao adicionar um exercício, o coach escolhe a fase e pode escrever uma observação; a planilha passa a mostrar os exercícios agrupados nas 5 fases (ordem canônica, cada fase com sua pergunta-guia, "nenhum exercício nesta fase" quando vazia, grupo "Sem fase" ao fim); e o coach escreve/edita a apresentação do treino, exibida no topo. Comportamentos [F1] 1, 2, 3, 4, 9, 10 (coach) e 7 (apresentação).

## Depende de
01 (fase no item + serviço + apresentação + agrupamento)

## Status
planejada

## Especificação funcional
Reaproveita a rota e o template que já existem (`treino_detail` + `treinos/aluno_detalhe.html`). O serviço da issue 01 já entrega tudo: `agrupar_itens_por_fase`, `add_item_to_treino(..., fase=...)`, `set_apresentacao`, `FASE_OPCOES`/`FASE_LABELS`. O campo de observação por item **já existe** no form e na exibição — manter.

- **Agrupamento na planilha:** `treino_detail` passa a montar `fases = agrupar_itens_por_fase(detalhe["itens"])`, mapeando os itens de cada grupo por `_to_item_display` (que passa a incluir `fase`/`fase_label`). O template renderiza um **bloco por fase** na ordem canônica: cabeçalho com o `fase_label` + a `fase_pergunta`; os exercícios daquela fase (mesma tabela/linha de hoje, com remover); "nenhum exercício nesta fase" quando o grupo está vazio. O grupo **"Sem fase"** só aparece quando há itens sem fase (o serviço já cuida disso).
- **Adicionar com fase:** o formulário de adicionar ganha um `<select name="fase">` (opção "—" para sem fase + as 5 de `FASE_OPCOES`). A rota `add_item_route` passa `fase` para `add_item_to_treino`. Fase inválida → re-render 400 com a mensagem (como já faz para outros erros). Observação segue como está.
- **Apresentação:** no topo, mostra a apresentação atual (`treino.observacao`) ou "sem registro"; um formulário (textarea) permite editar. Nova rota `POST /alunos/{aluno_id}/treino/{treino_id}/apresentacao` → `set_apresentacao(treino_id, texto)` → 303 de volta à planilha; 404 (get-or-404) quando o aluno/treino não confere, como nas outras rotas.
- **Isolamento/ownership:** mantém o padrão atual (get_aluno 404; `detalhe["aluno_id"] != aluno_id` → 404). Nada de regra no template (thin client).

Casos de borda: treino sem exercícios → 5 fases vazias com "nenhum exercício"; fase "—" → item em "Sem fase"; fase inválida via form adulterado → 400 sem gravar; apresentação vazia → "sem registro".

## Pré-condições
- Issue 01 concluída (serviço com fases, agrupamento, `set_apresentacao`; coluna `fase`). A rota `treino_detail` e `treinos/aluno_detalhe.html` existem. Auth: coach (rotas da ficha).

## Arquivos a modificar
- `kairos/treinos/routes.py` — importar `agrupar_itens_por_fase`, `set_apresentacao`, `FASE_OPCOES`, `FASE_LABELS`; `_to_item_display` inclui `fase`/`fase_label`; `_FASE_OPCOES_DISPLAY = [(v, FASE_LABELS[v]) for v in FASE_OPCOES]`; `treino_detail` passa `fases` (grupos com itens já em display) + `fase_opcoes` + `apresentacao` no contexto (no lugar de `itens`); `add_item_route` aceita `fase: Optional[str] = Form(None)` e repassa; re-render de erro usa os mesmos `fases`/`fase_opcoes`; nova rota `POST .../apresentacao` (`set_apresentacao`).
- `kairos/templates/treinos/aluno_detalhe.html` — apresentação (exibir + form de editar); render agrupado por fase (bloco com label + pergunta-guia; "nenhum exercício nesta fase"); `<select name="fase">` no form de adicionar. Reusar classes existentes (`planilha`, `table-wrap`, `field`, `coming-soon`, `message-error`, `card-line-dim`, `item-obs`).

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): contexto agrupado + `fase` no add + rota da apresentação em `kairos/treinos/routes.py`.
- **frontend** (`frontend-writer`): `treinos/aluno_detalhe.html` (apresentação, blocos de fase, select de fase).
- **testes** (`teste-writer`): `tests/test_treino_coach_fases.py` — GET mostra as fases com pergunta-guia; adicionar com `fase` faz o exercício aparecer sob a fase certa; adicionar com fase inválida → 400 sem gravar; `POST .../apresentacao` grava e exibe; 404 para aluno/treino inexistente. Coach auto-logado (conftest). Suíte anterior verde.
