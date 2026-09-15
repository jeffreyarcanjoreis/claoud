# Detalhe da avaliação com Δ e IMC

## Descrição
Comportamentos 8, 9, 10, 11, 12: o detalhe de uma avaliação mostra todas as métricas; para cada uma, o Δ vs a avaliação anterior do mesmo aluno (calculado, nunca guardado); a primeira avaliação aparece sem Δ; mostra o IMC calculado de peso e altura ("sem registro" se faltar algum); id inexistente → 404.

## Depende de
04-avaliacao-formulario

## Especificação funcional
- `GET /alunos/{id}/avaliacoes/{avaliacao_id}` mostra o detalhe de uma avaliação (dentro da ficha): todas as métricas registadas (peso, altura, % gordura, massa magra, massa gorda) e o IMC.
- Para cada métrica, mostra o **Δ vs a avaliação anterior** do mesmo aluno (a avaliação com a maior data anterior à desta; desempate por id). Δ = valor atual − valor anterior; se faltar o valor atual ou o anterior, não mostra Δ. O sinal é visível (subiu / desceu / igual).
- A **primeira** avaliação do aluno (sem anterior) mostra as métricas sem Δ.
- **IMC calculado** de peso e altura (peso_kg / (altura_cm/100)²), nunca guardado; se faltar peso ou altura → "sem registro".
- Métrica NULL → "sem registro".
- `avaliacao_id` inexistente → 404 no visual da marca.
- Regra de ouro: Δ e IMC são calculados na hora, jamais lidos de coluna.

## Pré-condições
- Issue 04 concluída: há como criar avaliações; `ficha_layout`, `get_avaliacao`, `list_avaliacoes` disponíveis.

## Arquivos a criar
- `kairos/templates/avaliacoes/detalhe.html` — `{% extends "alunos/ficha_layout.html" %}`; no bloco: a data, cada métrica com o seu valor (ou "sem registro") e o Δ (com sinal/cor: subiu, desceu, igual), e o IMC. Link "Voltar às avaliações".
- `tests/test_avaliacao_detalhe.py` — detalhe mostra as métricas; com duas avaliações, a segunda mostra o Δ correto de cada métrica vs a primeira; a primeira (sozinha) não mostra Δ; IMC calculado corretamente; sem peso/altura → IMC "sem registro"; métrica NULL → "sem registro"; `/alunos/{id}/avaliacoes/999` → 404.

## Arquivos a modificar
- `kairos/avaliacoes/service.py` — adicionar a regra de negócio dos derivados: uma função que, dada uma avaliação, encontra a **anterior** do mesmo aluno (maior data < a desta; desempate por id) e devolve o detalhe com, por métrica, o valor atual, o valor anterior e o Δ (ou None), mais o IMC calculado. Ex.: `get_avaliacao_detail(avaliacao_id) -> dict | None`. Tudo calculado, nada gravado. Sem log (leitura).
- `kairos/avaliacoes/routes.py` — adicionar `GET /alunos/{aluno_id}/avaliacoes/{avaliacao_id}` (`avaliacao_id: int`): get_aluno (404) + `get_avaliacao_detail` (404 se None) → renderiza `avaliacoes/detalhe.html` com header + subtab='avaliacoes'. Registada DEPOIS de `/avaliacoes/nova`.
- `kairos/static/css/components.css` — estilo do Δ (subiu/desceu/igual) e da linha de métrica do detalhe, usando tokens (ex.: verde-sálvia/argila para direção, ou só sinais + ouro). Sem cores fora dos tokens.

## Camadas envolvidas
serviço (Δ + IMC), aplicação (rota de detalhe), frontend (detalhe.html + CSS do Δ), teste

## Status
concluída
