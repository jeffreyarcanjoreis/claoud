# Seletor de métrica do gráfico

## Descrição
Comportamentos 4 e 5: botões para trocar a métrica mostrada (Peso, Massa magra, % Gordura, IMC); clicar troca a série visível sem recarregar a página (JS puro, sem lógica de negócio no cliente); o botão da métrica atual fica destacado.

## Depende de
02-avaliacao-grafico-svg

## Especificação funcional
- Acima do gráfico, um seletor com 4 botões: **Peso · Massa magra · % Gordura · IMC**.
- Por padrão, **Peso** está ativo (destacado) e é a série visível — coerente com a issue 02.
- Clicar num botão mostra o grupo `<g data-metric>` correspondente, esconde os outros três, e destaca o botão clicado — **sem recarregar a página** (JS puro).
- Sem lógica de negócio no cliente: o JS só alterna `display` dos grupos e a classe ativa dos botões; os dados e a geometria já vieram do servidor (issues 01-02).
- O seletor só aparece quando há gráfico (chart não vazio).
- Caso de borda: trocar para uma métrica sem dados mostra o "Sem dados para esta métrica." já renderizado nesse grupo (issue 02).
- Nenhum comportamento existente muda. 171 testes verdes.

## Pré-condições
- Issue 02 concluída: os 4 grupos `<g data-metric="peso|massa_magra|gordura_pct|imc">` estão no SVG (só peso visível), dentro do `.chart-panel`.

## Arquivos a criar
- `tests/test_avaliacao_grafico_seletor.py` — o `.metric-selector` tem 4 botões com `data-metric-btn` = peso/massa_magra/gordura_pct/imc e os rótulos curtos (Peso, Massa magra, % Gordura, IMC); o botão Peso tem a classe ativa por padrão; o seletor NÃO aparece quando o aluno não tem avaliações; o `<script>` do toggle está presente na página. (A troca em si é verificada no browser — não dá em teste server-side.)

## Arquivos a modificar
- `kairos/templates/avaliacoes/lista.html` — dentro do `.chart-panel` (só quando `not chart.empty`), acrescentar antes do `<svg>` um `<div class="metric-selector">` com um `<button type="button" class="metric-btn{% if m.visible %} on{% endif %}" data-metric-btn="{{ m.key }}">{{ btn_label }}</button>` por métrica (rótulos curtos via um dict `{'peso':'Peso','massa_magra':'Massa magra','gordura_pct':'% Gordura','imc':'IMC'}` no template — presentação, sem tocar na rota). Acrescentar um `<script>` inline (vanilla, sem framework): ao clicar num `.metric-btn`, define `display` do `g[data-metric=key]` para visível e dos outros para `none`, e move a classe `on` para o botão clicado. Usa `aria-pressed` nos botões para acessibilidade.
- `kairos/static/css/components.css` — `.metric-selector` (linha de botões, gap) e `.metric-btn` / `.metric-btn.on` (no estilo dos filtros/abas: bone-dim → bone; ativo com fundo/realce em ouro discreto), só tokens.

## Camadas envolvidas
frontend (botões + JS puro + CSS), teste

## Status
concluída
