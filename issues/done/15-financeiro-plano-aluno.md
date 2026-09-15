# Financeiro — plano & valor do aluno (a base)

## Descrição
A base do Financeiro: cada aluno passa a ter um **plano** (formato + valor + ciclo + início), ancorado na pirâmide do modelo de negócio (Digital · Grupo · 1-a-1). Isso transforma "alunos ativos" em **receita recorrente** e destrava os indicadores. Primeira peça do épico Financeiro (mapa: 1 plano → 2 recebimentos → 3 despesas → 4 painel do mês → 5 leads).

## Decisões (com o PO)
- Começar pela peça 1 (plano do aluno) — é a base que faz o Financeiro virar número real (regra 6: sem plano, nada de receita inventada).
- **valor = valor mensal (R$/mês)** — o valor recorrente, para dar MRR direto. (Se o PO pensa em pacote por ciclo, o mensal = pacote ÷ meses.) **Confirmar na aprovação.**
- Formato reflete a pirâmide: digital · grupo · individual (1-a-1).
- Um plano por aluno (o atual). Histórico de migração na pirâmide = evolução futura.

## Especificação funcional
- A sub-aba **"Financeiro"** da ficha do aluno (hoje "em breve") passa a mostrar o plano do aluno (formato, valor mensal, ciclo, início, observação) ou um estado "sem plano", com um formulário para **definir/editar** o plano; e uma ação para **remover** o plano.
- Definir/editar exige **formato** válido (digital/grupo/individual) e **valor** (> 0); ciclo (meses), início e observação são opcionais. Formato inválido ou valor ausente/≤0 → recusa com mensagem, sem gravar. Vazios opcionais → NULL / "sem registro".
- Um aluno tem no máximo um plano (upsert: definir de novo atualiza o existente).
- **Indicadores** (agregado sobre alunos ATIVOS com plano): **MRR** = soma dos valores mensais; **ticket médio** = MRR ÷ nº de ativos com plano (ou "sem registro" quando não há); **nº de ativos com plano**.
- O painel **`/financeiro`** passa a liderar com esses indicadores (números reais; 0/sem registro quando não há planos — regra 6), mantendo abaixo a lista das próximas peças (Recebimentos, Despesas, Novos contatos/leads — em breve).
- O tile **"Financeiro"** do Início mostra o **MRR** (ex.: "R$ 1.200,00") em vez de "em breve".
- Valores exibidos em formato brasileiro (R$ 1.234,56).
- id de aluno inexistente nas rotas da sub-aba → 404.
- Os 361 testes anteriores continuam verdes, exceto os ajustes intencionais em `/financeiro` (deixa de ser página "em breve") e no tile do Início.

## Pré-condições
- Ficha do aluno com `ficha_layout.html` (sub-aba "Financeiro" já existe, marcada "em breve", rota `/alunos/{id}/financeiro` via `_render_ficha`). Head de migração em 0011. 361 testes verdes.

## Arquivos a criar
- `migrations/versions/0012_create_planos_aluno.py` — tabela `planos_aluno` (id; aluno_id FK NOT NULL **unique**; formato String(20) NOT NULL; valor Numeric(10,2) NOT NULL; ciclo_meses Integer NULL; inicio Date NULL; observacao Text NULL; created_at DateTime server_default now). Tipos portáveis (rule 4). head → 0012.
- `kairos/financeiro/__init__.py`, `models.py` (`PlanoAluno`), `service.py`, `routes.py`.
  - `service.py`: `ValidationError`; `FORMATOS_VALIDOS=("digital","grupo","individual")`; `set_plano(aluno_id, *, formato, valor, ciclo_meses, inicio, observacao) -> dict` (upsert: valida formato/valor>0; parseia ciclo/inicio opcionais; se já existe plano do aluno, atualiza; senão cria); `get_plano(aluno_id) -> Optional[dict]`; `remover_plano(aluno_id) -> bool`; `resumo_financeiro() -> dict` (`{mrr, ticket_medio, alunos_com_plano}` — join `PlanoAluno` com `Aluno` filtrando `status=="active"`; mrr = soma de valor; ticket_medio = mrr/contagem ou None; usa Decimal).
  - `routes.py`: `GET /alunos/{id}/financeiro` (sub-aba: plano ou "sem plano" + form; 404 se aluno ausente), `POST /alunos/{id}/financeiro` (set_plano; erro → re-render com erro+valores, 400; sucesso → redirect 303), `POST /alunos/{id}/financeiro/remover` (remover_plano; redirect 303). Reaproveita `ficha_header`.
- `kairos/templates/alunos/financeiro.html` — estende `alunos/ficha_layout.html`; mostra o plano (formato label, valor R$, ciclo, início, obs) ou "sem plano"; formulário definir/editar (select formato; input valor; input ciclo; input date início; textarea obs); botão "Remover plano" quando há plano.
- `kairos/templates/painel/financeiro.html` — página do painel: bloco de indicadores (MRR, ticket médio, nº de ativos com plano) + a lista das próximas peças (em breve). (Substitui o uso de `area_em_breve.html` para `/financeiro`.)
- `tests/test_plano_aluno_model.py` e `tests/test_financeiro.py` (modelo + serviço/rotas + indicadores + Início/painel).

## Arquivos a modificar
- `kairos/main.py` — registrar `financeiro_router`.
- `kairos/painel/routes.py` — `financeiro()` passa a renderizar `painel/financeiro.html` com `resumo_financeiro()` formatado (R$); `inicio_context()`/o tile do Início recebe o MRR formatado (o tile "Financeiro" deixa de ser "em breve").
- `kairos/templates/painel/inicio.html` — o tile "Financeiro" mostra o MRR (link para `/financeiro`).
- `kairos/templates/alunos/ficha_layout.html` — a sub-aba "Financeiro" perde o marcador "em breve".
- `kairos/static/css/components.css` — estilos do plano/indicadores se necessário (reusar o que der).
- Testes de head (9 arquivos: `test_scaffold`, `test_sessao_agendada_model`, `test_foto_modelo`, `test_avaliacao_model`, `test_perimetria_model`, `test_exercicio_model`, `test_treino_model`, `test_sessao_realizada_model`, `test_tarefa_model`) — HEAD_REVISION "0011"→"0012"; scaffold: simulação recua para '0011' e `DROP TABLE planos_aluno`.
- `tests/test_areas_em_breve.py` — `/financeiro` deixa de ser página "em breve" (sai das listas parametrizadas; asserções passam a cobrir os indicadores + itens futuros); `tests/test_inicio.py` — o tile "Financeiro" mostra MRR, não "em breve".

## Camadas envolvidas
banco/migração, serviço, aplicação (rotas + painel financeiro + Início), frontend (sub-aba + painel financeiro + tile + subnav), teste.

## Fora desta fatia
- Recebimentos/mensalidades (pago/pendente/atrasado) — peça 2.
- Despesas/saídas — peça 3.
- Painel completo do mês (entradas − saídas, quem sustenta, churn) — peça 4.
- Leads/novos contatos (Google Form) — peça 5.
- Histórico de planos / migração na pirâmide; parcelamento; moeda configurável.

## Status
concluída
