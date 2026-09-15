# Financeiro — gráficos (entradas × saídas + projeção)

## Descrição
Trocar as fileiras de números do painel `/financeiro` por **gráficos**: um retrospectivo (entradas × saídas por mês, que cresce com o uso) e um prospectivo (projeção da receita recorrente e dos alunos pagantes para os próximos meses). Mantém o **Resultado do mês** em destaque. Continuação natural da peça 4; é agregação + apresentação — **sem tabela nem migração**.

## Decisões (com o PO)
- Os **dois gráficos** (retrospectivo + prospectivo), com o Resultado do mês em destaque no topo.
- Verdade dos dados (regra 6): o retrospectivo **nasce quase vazio** (o financeiro começou a coletar agora) e enche mês a mês — real, só esparso no início. O prospectivo é calculado dos **planos atuais** ("se os planos continuarem"); a qualidade melhora quando os planos têm **início + ciclo** preenchidos (aí a projeção decai conforme os contratos terminam; sem esses dados, assume continuidade).
- Técnica: **SVG renderizado no servidor, sem biblioteca JS** (CSP), como o gráfico das avaliações. Tooltips nativos via `<title>` do SVG (sem JS). Cores da marca **validadas** com `scripts/validate_palette.js` da skill dataviz (entradas = sálvia, saídas = argila, projeção = ouro), com legenda + rótulos diretos (encoding secundário, não só cor). Tema escuro.

## Especificação funcional
- `/financeiro` (mês atual) mostra, de cima para baixo:
  - **Resultado do mês** em destaque (recebido − despesas; positivo sálvia / negativo argila) — mantido.
  - **Gráfico 1 — Entradas × Saídas (últimos 6 meses):** barras agrupadas por mês, duas séries (entradas em sálvia, saídas em argila), mesma escala em R$; legenda; rótulo do mês (mm/aa) no eixo; `<title>` por barra com o valor. Meses sem dado aparecem zerados (ou a janela mostra só os meses existentes) — nunca valor inventado. No começo, com só o mês atual, o gráfico mostra 1 grupo.
  - **Gráfico 2 — Projeção (próximos 6 meses):** a **receita recorrente prevista** por mês (série única, ouro), a partir dos planos ativos; o **nº de alunos pagantes previsto** aparece como rótulo em cada mês (NÃO como segundo eixo — regra "um eixo só" da dataviz). Um plano conta num mês futuro se aquele mês está dentro do seu contrato: com `inicio`+`ciclo_meses` → ativo enquanto `mês < inicio + ciclo`; sem esses campos → assume continuidade (conta em todos). 
  - **Quem sustenta o mês** (lista) e os **atalhos** (Recebimentos, Despesas) — mantidos. A caixa "por vir" com Leads — mantida.
  - As fileiras de tiles numéricos (recebido/despesas/a-receber e mrr/ticket/ativos) saem — a informação passa para os gráficos e o destaque; os números detalhados continuam nas páginas de Recebimentos e Despesas.
- Estados vazios honestos: sem nenhum pagamento/despesa/plano, os gráficos mostram um aviso "ainda sem dados para o período" em vez de eixos vazios.
- Os 433 testes anteriores continuam verdes (a página `/financeiro` muda — ajustar os testes que a checam ao novo conteúdo, mantendo o essencial: Resultado + acesso a Recebimentos/Despesas).

## Pré-condições
- Peças 1-4 do Financeiro concluídas; `panorama_mes`, `recebimentos_do_mes`, `total_despesas_mes`, planos/pagamentos/despesas no service. 433 testes verdes. Head de migração continua 0014 (sem banco).
- Skill dataviz carregada; validar a paleta (sálvia/argila/ouro) com o script antes de fechar as cores.

## Arquivos a criar
- `kairos/financeiro/graficos.py` — helpers de APRESENTAÇÃO puros (sem DB): recebem as séries do service e devolvem a geometria do SVG (pontos/barras/escala/rótulos), no molde de `avaliacoes/routes.py::_build_chart`. Ex.: `grafico_entradas_saidas(serie) -> dict` e `grafico_projecao(serie) -> dict` (viewBox, barras com x/y/altura/cor, ticks, rótulos, legenda).
- `tests/test_financeiro_series.py` — cobre as funções de série do service.
- `tests/test_financeiro_graficos.py` — cobre a geometria (helpers de graficos.py) e a rota `/financeiro` renderizando os `<svg>`.

## Arquivos a modificar
- `kairos/financeiro/service.py` — **adicionar** (só leitura): `serie_entradas_saidas(meses=6) -> list[{ano, mes, recebido: Decimal, despesas: Decimal}]` (soma de pagamentos e despesas por mês, para os últimos `meses` meses incluindo o atual); `projecao_receita(meses=6) -> list[{ano, mes, receita: Decimal, alunos: int}]` (dos planos ativos: para cada mês futuro, soma dos valores e contagem dos planos ainda dentro do contrato — `inicio`+`ciclo_meses` quando existirem, senão continuidade).
- `kairos/painel/routes.py` — a rota `GET /financeiro` passa a montar, além do destaque de Resultado, a geometria dos dois gráficos (via `financeiro/graficos.py`) e passar ao template. Reaproveita `_MESES`/`formatar_reais`.
- `kairos/templates/painel/financeiro.html` — renderizar os dois `<svg>` (com legenda, rótulos e `<title>` por marca), o Resultado em destaque, "Quem sustenta", atalhos e "por vir"; remover as duas fileiras de tiles numéricos.
- `kairos/static/css/components.css` — estilos dos gráficos (eixo/grade recessivos, legenda, cores por classe `.serie-entrada`/`.serie-saida`/`.serie-projecao`, rótulos), tema escuro; reusar tokens.
- `tests/test_painel_mes.py` / `tests/test_areas_em_breve.py` — ajustar asserções ao novo `/financeiro` (Resultado + `<svg>` + acesso a Recebimentos/Despesas; os labels dos tiles removidos saem das asserções).

## Camadas envolvidas
serviço (séries), apresentação (graficos.py — geometria SVG), aplicação (rota `/financeiro`), frontend (SVG no template + CSS), teste. **Sem banco/migração.**

## Fora desta fatia
- Filtros de intervalo / trocar a janela de meses pela interface; hover com JS (usamos `<title>` nativo); exportar; média móvel/tendência estatística sofisticada.
- Leads (peça 5).

## Status
concluída
