# Série temporal das avaliações (serviço)

## Descrição
Comportamentos 2, 7 e 10 (lado dos dados): uma função no serviço de avaliações que devolve a série cronológica (mais antiga → mais recente) do aluno, com o valor de cada métrica por avaliação — Peso, Massa magra, % Gordura e IMC (o IMC calculado por avaliação, nunca guardado). Onde a métrica é NULL, o ponto fica marcado como ausente (não vira zero).

## Depende de
nenhuma

## Especificação funcional
- `avaliacao_series(aluno_id) -> list[dict]` devolve as avaliações do aluno em **ordem cronológica ascendente** (data asc; desempate por id asc). Cada item: `{data, peso, massa_magra, gordura_pct, imc}`.
  - `peso`, `massa_magra`, `gordura_pct` são o valor do banco (Decimal) ou `None` quando NULL — nunca convertidos para 0.
  - `imc` é calculado de peso e altura de cada avaliação (reusa `_calcular_imc`), `None` se faltar peso ou altura. Nunca lido de coluna.
  - (altura e massa_gorda não fazem parte do gráfico; altura entra só no cálculo do IMC.)
- Aluno sem avaliações → lista vazia `[]`.
- Operação de leitura: sem log.

## Pré-condições
- Fatia 3 (Avaliação) concluída: modelo, `list_avaliacoes`, `_calcular_imc`, `_to_dict` existem. 158 testes verdes.

## Arquivos a criar
- `tests/test_avaliacao_serie.py` — aluno sem avaliações → []; com 3 avaliações criadas fora de ordem de data, a série volta em ordem asc de data; o IMC é calculado corretamente por ponto; uma métrica NULL fica None (não 0); IMC None quando falta altura ou peso.

## Arquivos a modificar
- `kairos/avaliacoes/service.py` — acrescentar `avaliacao_series(aluno_id)`: `select(Avaliacao).where(Avaliacao.aluno_id == aluno_id).order_by(Avaliacao.data.asc(), Avaliacao.id.asc())`; para cada, montar o dict com `data`, `peso`, `massa_magra`, `gordura_pct` (primitivos/Decimal ou None) e `imc=_calcular_imc(av.peso, av.altura)`. Dentro de `session_scope`, primitivos extraídos antes de fechar. Sem log.

## Camadas envolvidas
serviço, teste

## Status
concluída
