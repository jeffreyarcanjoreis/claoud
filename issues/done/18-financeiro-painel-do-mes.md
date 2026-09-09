# Financeiro — painel do mês (peça 4)

## Descrição
O panorama que junta tudo: **recebido − despesas = resultado do mês**, mais a receita recorrente, o que falta receber e quem sustenta o mês. Peça 4 do épico Financeiro (1 plano ✓ · 2 recebimentos ✓ · 3 despesas ✓ · **4 painel do mês** · 5 leads). É só **agregação** — não cria tabela nem migração.

## Decisões (com o PO)
- É o conteúdo natural da página `/financeiro`: ela deixa de ser só 3 indicadores + botões e vira o **painel do mês** de verdade (mês atual do servidor), mantendo os botões para Recebimentos e Despesas.
- "Quem sustenta o mês" = a lista dos pagamentos do mês (quem já pagou), do maior para o menor. Churn/cancelados do mês fica de fora (não temos data de cancelamento — só o status ativo/inativo; seria dado inventado).

## Especificação funcional
- `/financeiro` mostra, para o **mês atual**:
  - **Resultado do mês** (destaque): **recebido − despesas**; marcado como positivo ou negativo.
  - **Recebido** (soma dos pagamentos do mês) e **Despesas** (soma das despesas do mês).
  - **A receber** (pendente: soma dos valores de plano dos ativos sem pagamento no mês).
  - **Receita recorrente (MRR)**, **ticket médio** e **ativos com plano** (os indicadores que já existem).
  - **Quem sustenta o mês** — lista dos alunos que pagaram no mês (nome + valor), do maior para o menor; estado vazio quando ninguém pagou ainda.
  - Os **botões** "Recebimentos / mensalidades" e "Despesas (saídas)" continuam; a caixa "Ainda por vir" fica só com os Leads.
- Todos os valores em R$ brasileiro; 0/sem registro quando não há dados (regra 6). Nada inventado.
- Os 427 testes anteriores continuam verdes (a página `/financeiro` muda — os testes que a checam serão ajustados para o novo conteúdo, mantendo o essencial: indicadores + links de recebimentos/despesas).

## Pré-condições
- Peças 1-3 concluídas: `resumo_financeiro`, `resumo_recebimentos_mes`, `recebimentos_do_mes`, `total_despesas_mes` no `kairos/financeiro/service.py`; painel `/financeiro` com indicadores + botões. 427 testes verdes. (Head de migração continua 0014 — sem mudança de banco.)

## Arquivos a criar
- `tests/test_painel_mes.py` — cobre `panorama_mes` (resultado = recebido − despesas; a receber; quem sustenta ordenado desc; casos vazios) e a rota `/financeiro` (mostra "Resultado", "Recebido", "Despesas", "A receber", e os nomes de quem pagou).

## Arquivos a modificar
- `kairos/financeiro/service.py` — **adicionar** `panorama_mes(ano, mes) -> dict`: combina `resumo_recebimentos_mes(ano,mes)` (recebido, pendente), `total_despesas_mes(ano,mes)` (despesas), `resumo_financeiro()` (mrr, ticket_medio, alunos_com_plano) e `recebimentos_do_mes(ano,mes)` (para "sustentam" = os `pago=True`, ordenados por valor_pago desc: lista de `{aluno_nome, valor_pago}`). Devolve `{recebido, despesas, resultado (=recebido−despesas), a_receber (=pendente), mrr, ticket_medio, alunos_com_plano, sustentam}` (Decimals + lista). Só leitura, sem log.
- `kairos/financeiro/routes.py` (ou `kairos/painel/routes.py`, onde está a rota `/financeiro`) — a rota `GET /financeiro` passa a montar o contexto do painel do mês a partir de `panorama_mes(hoje.year, hoje.month)`, formatando com `formatar_reais` (o resultado com flag `resultado_positivo`), o `mes_label`, e a lista `sustentam` (nome + valor R$). **Nota:** hoje `/financeiro` vive em `kairos/painel/routes.py`; mover para o `financeiro_router` é opcional — manter onde está e só enriquecer o contexto é o mais simples.
- `kairos/templates/painel/financeiro.html` — reescrever para o painel do mês: título com o mês; o Resultado em destaque (classe positivo/negativo); tiles/linhas de Recebido, Despesas, A receber; os indicadores MRR/ticket/ativos; a seção "Quem sustenta o mês" (lista); os botões de Recebimentos/Despesas; e a caixa "Ainda por vir" só com Leads.
- `kairos/static/css/components.css` — estilo do Resultado em destaque (positivo verde-sálvia / negativo argila) e da lista "quem sustenta", reusando o que der.
- `tests/test_areas_em_breve.py` (e o que mais checar `/financeiro`) — ajustar as asserções ao novo conteúdo (manter: indicadores + "Recebimentos"/"Despesas" acessíveis).

## Camadas envolvidas
serviço (panorama_mes), aplicação (rota `/financeiro`), frontend (financeiro.html + CSS), teste. **Sem banco/migração.**

## Fora desta fatia
- Navegar por meses passados/futuros; gráficos/evolução; churn/cancelados do mês (precisa de data de cancelamento); exportar/relatórios.
- Leads (peça 5).

## Status
concluída
