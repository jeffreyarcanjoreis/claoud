# Perimetria no detalhe com Δ

## Descrição
Comportamentos 6, 7, 8, 9, 10: o detalhe da avaliação mostra uma secção de perimetria com cada segmento medido (valor + Δ vs o mesmo segmento na avaliação anterior do aluno, calculado nunca guardado); avaliação sem perimetria mostra "sem registro"; primeira avaliação sem Δ; segmento sem anterior não mostra Δ.

## Depende de
02-perimetria-servico-guardar

## Especificação funcional
- O detalhe da avaliação (`/alunos/{id}/avaliacoes/{id}`) ganha uma secção "Perimetria (cm)": cada segmento medido nesta avaliação, com o seu valor e o Δ vs o MESMO segmento na avaliação anterior do aluno.
- Δ por segmento = valor atual − valor do mesmo segmento na anterior, quando ambos existem; senão não mostra Δ (segmento sem par na anterior, ou sem avaliação anterior). Calculado na hora, nunca guardado.
- A primeira avaliação do aluno mostra a perimetria sem Δ (não há anterior).
- Se a avaliação não tem nenhuma perimetria, a secção mostra "sem registro" (nunca inventa segmentos/valores).
- Só aparecem os segmentos que esta avaliação mediu (linhas existentes); segmento sem valor não aparece (é a regra pai-filho: sem valor, sem linha).
- `avaliacao_id` inexistente → 404 (já tratado).

## Pré-condições
- Issue 02 concluída: `list_perimetria`, `PERIMETRIA_SEGMENTOS`. `get_avaliacao_detail` já calcula a anterior e reusa helpers de formatação (`_format_valor`, `_format_delta`) na rota. `detalhe.html` existe. 192 testes verdes.

## Arquivos a modificar
- `kairos/avaliacoes/service.py` — em `get_avaliacao_detail`, acrescentar ao dict retornado a chave `"perimetria"`: uma lista, em ordem canónica, de `{segmento, valor, delta}` para cada segmento medido NA avaliação atual. Implementação: `perim_atual = list_perimetria(current_id)`; `perim_ant = {r["segmento"]: r["valor"] for r in list_perimetria(previous_id)}` se houver anterior, senão `{}`; para cada `r` em `perim_atual`, `delta = r["valor"] - perim_ant[r["segmento"]]` se o segmento existe na anterior, senão `None`. (list_perimetria abre a sua própria sessão; chamar depois do session_scope do detail, como já se faz o cálculo dos deltas antropométricos fora da sessão.) Tudo calculado, nada guardado.
- `kairos/avaliacoes/routes.py` — em `_to_detail_display`, formatar `av["perimetria"]` numa lista de exibição: para cada item, `{label: segmento, valor: _format_valor(valor), delta: _format_delta(delta)[0] ou None, direcao: _format_delta(delta)[1]}` (reusar os helpers já existentes). Passar essa lista (ex.: `av["perimetria"]` no dict de exibição) ao template. Incluir também um flag/lista vazia para o caso "sem perimetria".
- `kairos/templates/avaliacoes/detalhe.html` — depois das métricas antropométricas + IMC, uma secção `<h3>Perimetria (cm)</h3>`: se há itens, uma lista (reusa `.profile`/`.row`/`.k`/`.v` + o `.delta` já estilizado) com cada segmento (`.k` = label, `.v` = valor + `<span class="delta delta-{{direcao}}">` quando há delta); se não há itens, uma linha "sem registro" (`.none`).

## Arquivos a criar
- `tests/test_perimetria_detalhe.py` — cria aluno + 2 avaliações, ambas com Cintura (ex.: 84 e 82). No detalhe da 2ª: a secção Perimetria mostra "Cintura", o valor 82 e o Δ (−2). No detalhe da 1ª (sem anterior): mostra a perimetria sem Δ. Segmento medido só na 2ª (não na 1ª): sem Δ nessa linha. Avaliação sem perimetria nenhuma: a secção mostra "sem registro". `/alunos/{id}/avaliacoes/999` → 404 (regressão).

## Camadas envolvidas
serviço (Δ da perimetria), aplicação (formatação no detalhe), frontend (secção no detalhe), teste

## Status
concluída
