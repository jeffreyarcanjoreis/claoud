# Financeiro — despesas / saídas (peça 3)

## Descrição
O outro lado do caixa: registrar os **gastos** do negócio por categoria e ver o **total do mês**. Peça 3 do épico Financeiro (mapa: 1 plano ✓ → 2 recebimentos ✓ → 3 despesas → 4 painel do mês → 5 leads). Independe do plano — fatia curta e autocontida.

## Decisões (com o PO)
- Segunda das duas fatias combinadas ("as duas em sequência"): Recebimentos (feita) e agora Despesas, cada uma com seu /plan.
- Registro **manual** de despesas; visão do **mês atual** (como os recebimentos). Navegar por meses passados/futuros e despesas recorrentes = evolução futura.

## Especificação funcional
- Nova visão de painel **`/financeiro/despesas`** mostra as **despesas do mês atual** (mês do servidor): uma lista das despesas (data, descrição, categoria quando houver, valor) e o **total do mês** (R$) no topo.
- Um formulário para **registrar uma despesa**: data, descrição, categoria (opcional), valor.
- Cada despesa da lista tem uma ação para **remover**.
- Registrar exige **data** válida, **descrição** (não vazia) e **valor** > 0; categoria opcional de um conjunto (aluguel · equipamento · software · divulgação · formação · outros); inválidos → recusa com mensagem, sem gravar. Vazios opcionais → NULL / "sem registro".
- As despesas aparecem da mais recente para a mais antiga (data desc).
- O painel `/financeiro` passa a **linkar** "Despesas" (hoje só texto) para `/financeiro/despesas`.
- Números reais (regra 6): total 0 quando não há despesas; nada inventado.
- Os 407 testes anteriores continuam verdes.

## Pré-condições
- Peças 1 e 2 do Financeiro concluídas; módulo `kairos/financeiro/` com models/service/routes; painel `/financeiro`. Head de migração em 0013. 407 testes verdes.

## Arquivos a criar
- `migrations/versions/0014_create_despesas.py` — tabela `despesas` (id; data Date NOT NULL; descricao String(200) NOT NULL; categoria String(30) NULL; valor Numeric(10,2) NOT NULL; observacao Text NULL; created_at DateTime server_default now). Tipos portáveis. head → 0014.
- `kairos/templates/painel/despesas.html` — visão do mês (total no topo; form de registrar: data, descrição, categoria select opcional, valor; lista das despesas do mês com remover; estado vazio "Nenhuma despesa neste mês.").
- `tests/test_despesa_model.py`, `tests/test_despesas.py`.

## Arquivos a modificar
- `kairos/financeiro/models.py` — **adicionar** o modelo `Despesa` (mesmo módulo).
- `kairos/financeiro/service.py` — **adicionar**: `CATEGORIAS_DESPESA=("aluguel","equipamento","software","divulgacao","formacao","outros")`; `registrar_despesa(*, data, descricao, categoria, valor, observacao) -> dict` (valida data/descrição/valor>0, categoria opcional no conjunto); `remover_despesa(id) -> bool`; `get_despesa(id)`; `despesas_do_mes(ano, mes) -> list` (data desc); `total_despesas_mes(ano, mes) -> Decimal`.
- `kairos/financeiro/routes.py` — **adicionar** (mesmo `router`): `GET /financeiro/despesas` (mês atual: total + lista + form), `POST /financeiro/despesas` (registrar; erro → re-render com mensagem, 400; sucesso → redirect 303), `POST /financeiro/despesas/{despesa_id}/remover` (redirect 303). Helper de display (categoria label, valor R$, data dd/mm/aaaa) e o `_MESES_PT` já existente reaproveitado.
- `kairos/templates/painel/financeiro.html` — o item "Despesas" vira link para `/financeiro/despesas`.
- `kairos/static/css/components.css` — estilos se necessário (reusar).
- Testes de head (11 arquivos: os 10 de antes + `test_pagamento_model`) — HEAD_REVISION "0013"→"0014"; scaffold: simulação recua para '0013' e `DROP TABLE despesas`.

## Camadas envolvidas
banco/migração, serviço, aplicação (rotas + painel), frontend (despesas.html + link), teste.

## Fora desta fatia
- Navegar por meses; despesas recorrentes/parceladas; anexar recibo; relatórios por categoria.
- Painel do mês completo (peça 4 — junta recebido − despesas = resultado), leads (peça 5).

## Status
concluída
