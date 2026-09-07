# Gráfico SVG de evolução

## Descrição
Comportamentos 1, 2, 3, 6, 7, 8, 9, 11: na página de avaliações, um gráfico de linha em SVG renderizado no servidor mostra a evolução ao longo do tempo, ao lado da lista (duas colunas; empilha no telemóvel). As 4 séries são pré-desenhadas, cada uma com a sua escala vertical, só o Peso visível por padrão; NULL vira lacuna na linha; 0 avaliações → estado vazio; 1 avaliação → ponto único; cores e tipografia da marca.

## Depende de
01-avaliacao-serie-servico

## Especificação funcional
- A página `/alunos/{id}/avaliacoes` passa a ter duas colunas: a lista de avaliações à esquerda, o painel do gráfico à direita. Em telas estreitas, o gráfico fica abaixo da lista.
- O gráfico é um SVG de linha (evolução no tempo), renderizado no servidor. As avaliações vão da esquerda (mais antiga) para a direita (mais recente).
- As 4 séries (Peso, Massa magra, % Gordura, IMC) são pré-desenhadas no SVG, cada uma no seu grupo (`<g data-metric="...">`); só **Peso** visível por padrão (as outras `display:none`, prontas para o seletor da issue 03). Cada métrica usa a sua própria escala vertical.
- Ponto NULL vira **lacuna**: o marcador não é desenhado e a linha quebra ali (não liga através de um ponto ausente).
- Estados de borda: 0 avaliações → estado vazio ("sem dados para o gráfico"), sem eixos falsos; 1 avaliação → o ponto único, sem linha.
- IMC de cada ponto calculado (via a série do serviço), nunca guardado.
- Nenhum comportamento existente muda (a lista continua igual, agora dentro da coluna esquerda). 164 testes verdes.

## Decisões de dataviz (da skill)
- **Forma**: gráfico de linha (change-over-time). Só UMA série visível de cada vez (o seletor troca) → um único eixo Y de cada vez; nunca eixo duplo.
- **Cor**: uma cor de marca por métrica — Peso=`--gold`, Massa magra=`--sage`, % Gordura=`--clay`, IMC=`--bone-dim`. Cada uma aparece sozinha; a identidade vem do rótulo do seletor, não só da cor. Na execução, garantir contraste de cada linha sobre `--void`.
- **Marcas**: linha 2px, marcadores ≥8px, grelha/eixos recessivos (`--line`), rótulos de texto em `--bone`/`--bone-dim` (nunca na cor da linha), pontas arredondadas.
- **Rótulos diretos** de valor nos pontos (os dados são esparsos — um coach tem poucas avaliações); **sem tooltip de hover** — desvio consciente do "hover por padrão" da skill, justificado pela stack server-rendered/thin-client e pelo escopo (interação rica ficou fora). A **tabela acessível** dos mesmos dados já existe por construção: é a lista à esquerda.
- **Escuro**: desenhado para o fundo `--void` (não é um gráfico claro invertido).

## Pré-condições
- Issue 01 concluída: `avaliacao_series(aluno_id)` devolve a série cronológica com peso/massa_magra/gordura_pct/imc (None onde falta). `ficha_layout` e `lista.html` existem.

## Arquivos a criar
- `tests/test_avaliacao_grafico.py` — com 2 avaliações: o SVG do gráfico existe e tem os marcadores/linha da série Peso (nº de marcadores = nº de pontos com peso); a página tem a lista E o gráfico. Com 0 avaliações: estado vazio "sem dados". Com 1 avaliação: um marcador, sem `<polyline>`/linha. Métrica com NULL: a série dessa métrica tem menos pontos (lacuna). As 4 séries estão no HTML (grupos `data-metric`), só Peso sem `display:none`.

## Arquivos a modificar
- `kairos/avaliacoes/routes.py` — na rota da lista (`aluno_avaliacoes`), chamar `avaliacao_series(aluno_id)` e montar a **geometria** do gráfico num helper de apresentação `_build_chart(series) -> dict`: para cada métrica, min/max (ignorando None) → escala; pontos `{x, y, value_label, data_label}` (None omitido); segmentos da polyline (quebra em None); ticks dos eixos; flags `empty`/`single`. Passar isso a `lista.html`. (Geometria é presentação, não serviço.)
- `kairos/templates/avaliacoes/lista.html` — envolver a lista atual numa coluna esquerda e acrescentar a coluna direita com o SVG: os 4 grupos `<g data-metric>` (só Peso visível), eixos/grelha recessivos, marcadores, rótulos, e os estados vazio/único. Sem seletor ainda (issue 03).
- `kairos/static/css/components.css` — o grid de duas colunas (`.avaliacoes-layout`, colapsa para 1 coluna em telas estreitas), o painel do gráfico, e o estilo do SVG (grelha/eixos em `--line`, linha por métrica com a cor da marca via classe, marcadores, rótulos em texto). Só tokens.

## Camadas envolvidas
aplicação (geometria do gráfico na rota), frontend (lista em 2 colunas + SVG + CSS), teste

## Status
concluída
