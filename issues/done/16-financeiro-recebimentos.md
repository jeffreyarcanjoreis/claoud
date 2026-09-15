# Financeiro — recebimentos / mensalidades (peça 2)

## Descrição
Sobre a base (plano/valor do aluno), acompanhar **quem pagou** a mensalidade do mês e **quem está pendente**. Dá as **entradas** reais e a **inadimplência**. Segunda peça do épico Financeiro (mapa: 1 plano ✓ → 2 recebimentos → 3 despesas → 4 painel do mês → 5 leads).

## Decisões (com o PO)
- Vai ser feito junto com Despesas, mas **uma fatia de cada vez**: esta é Recebimentos; Despesas vem depois, com seu próprio /plan.
- Registro **manual** (o coach marca o pagamento recebido). "Atrasado" como estado próprio, geração automática de cobranças e navegação por meses = evolução futura; nesta fatia é **pago / pendente** do **mês atual**.
- Um pagamento por aluno por competência (mês/ano) — registrar de novo atualiza (upsert).

## Especificação funcional
- Nova visão de painel **`/financeiro/recebimentos`** mostra os **recebimentos do mês atual** (mês do servidor): para cada **aluno ativo com plano**, o valor do plano e se está **pago** (com valor e data) ou **pendente**.
- Cada linha **pendente** tem um formulário para **registrar o pagamento** (valor pré-preenchido com o valor do plano, editável; data pré-preenchida com hoje). Cada linha **paga** mostra valor/data e uma ação para **desfazer** (remover o pagamento).
- **Totais do mês:** **recebido** (soma dos pagamentos do mês) e **pendente** (soma dos valores de plano dos ativos sem pagamento no mês); ambos em R$.
- Registrar exige valor > 0; valor inválido/≤0 → recusa. Data de pagamento opcional (vazia → hoje? não: guarda a data informada; se vazia, usa a data de hoje). Competência = mês/ano atuais.
- A sub-aba **Financeiro** da ficha do aluno ganha, abaixo do plano, a **lista de recebimentos daquele aluno** (competência + valor + data), da mais recente para a mais antiga; estado vazio quando não há.
- O painel `/financeiro` passa a **linkar** "Recebimentos" (o item que hoje é "em breve") para `/financeiro/recebimentos`.
- Números reais (regra 6): 0/sem registro quando não há dados; nunca cobrança inventada. Só alunos **ativos com plano** entram na visão do mês (sem plano = sem mensalidade a cobrar).
- id de aluno inexistente nas rotas → 404; os 388 testes anteriores continuam verdes.

## Pré-condições
- Peça 1 concluída: `PlanoAluno` + `resumo_financeiro` + painel `/financeiro` + sub-aba Financeiro da ficha. Head de migração em 0012. 388 testes verdes.

## Arquivos a criar
- `migrations/versions/0013_create_pagamentos.py` — tabela `pagamentos` (id; aluno_id FK NOT NULL; ano Integer NOT NULL; mes Integer NOT NULL; valor Numeric(10,2) NOT NULL; data_pagamento Date NULL; observacao Text NULL; created_at DateTime server_default now; **UniqueConstraint(aluno_id, ano, mes)**). Tipos portáveis. head → 0013.
- `kairos/financeiro/models.py` — **adicionar** o modelo `Pagamento` (mesmo módulo do PlanoAluno).
- `kairos/financeiro/service.py` — **adicionar**: `registrar_pagamento(aluno_id, *, ano, mes, valor, data_pagamento, observacao) -> dict` (upsert por (aluno,ano,mes); valida valor>0, ano/mes; data vazia → hoje); `remover_pagamento(pagamento_id) -> bool`; `get_pagamento(pagamento_id)`; `pagamentos_do_aluno(aluno_id) -> list` (ordem competência desc); `recebimentos_do_mes(ano, mes) -> list` (para cada aluno ATIVO com plano: `{aluno_id, aluno_nome, valor_plano, pago, pagamento_id, valor_pago, data_pagamento}` via outer join `PlanoAluno`+`Aluno`(active) com `Pagamento` do mês); `resumo_recebimentos_mes(ano, mes) -> {recebido, pendente, total_esperado}` (Decimals).
- `kairos/financeiro/routes_recebimentos` — as rotas ficam em `kairos/financeiro/routes.py` (mesmo router) ou pode-se manter no mesmo arquivo: `GET /financeiro/recebimentos` (visão do mês atual + totais), `POST /financeiro/recebimentos` (registrar: Form aluno_id, valor, data_pagamento, observacao; competência = mês atual; erro → re-render com mensagem; sucesso → redirect 303), `POST /financeiro/recebimentos/{pagamento_id}/remover` (desfazer; redirect 303). (Rotas de painel — não são sub-aba de aluno; ficam num router do financeiro.)
- `kairos/templates/painel/recebimentos.html` — visão do mês (título com o mês/ano atual; totais recebido/pendente; lista dos ativos com plano: pagos vs pendentes, com form de registrar / ação de desfazer).
- `tests/test_pagamento_model.py`, `tests/test_recebimentos.py`.

## Arquivos a modificar
- `kairos/main.py` — se for criado um router novo do financeiro-painel, registrá-lo (ou reusar o existente).
- `kairos/painel/routes.py` — a rota `/financeiro` do painel continua; garantir link para `/financeiro/recebimentos`. (O template `painel/financeiro.html` passa a linkar o item "Recebimentos".)
- `kairos/templates/painel/financeiro.html` — o item "Recebimentos" vira link para `/financeiro/recebimentos`.
- `kairos/templates/alunos/financeiro.html` — adicionar a lista de recebimentos do aluno abaixo do plano (a rota GET da sub-aba passa a incluir `pagamentos_do_aluno`).
- `kairos/financeiro/routes.py` — a rota GET da sub-aba do aluno passa a incluir os recebimentos do aluno no contexto.
- `kairos/static/css/components.css` — estilos se necessário.
- Testes de head (10 arquivos: os 9 de antes + `test_plano_aluno_model`) — HEAD_REVISION "0012"→"0013"; scaffold: simulação recua para '0012' e `DROP TABLE pagamentos`.

## Camadas envolvidas
banco/migração, serviço, aplicação (rotas painel recebimentos + sub-aba), frontend (recebimentos.html + lista na sub-aba + link), teste.

## Fora desta fatia
- "Atrasado" como estado distinto (dias de vencimento); geração automática de cobranças; navegar por meses passados/futuros; parcelamento; recibos.
- Despesas (peça 3, próxima fatia), painel do mês (4), leads (5).

## Status
concluída
