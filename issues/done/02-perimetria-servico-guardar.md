# Serviço: guardar e listar perimetria

## Descrição
Comportamentos 2, 3, 4, 5 (lado da regra): ao criar uma avaliação, cada segmento com valor preenchido vira uma linha de perimetria ligada à avaliação; segmento vazio não vira linha (nem zero); valor negativo é recusado; valor aceita vírgula ou ponto (reusa o parser de número). Inclui obter a perimetria de uma avaliação. Lista fixa de segmentos-padrão em código.

## Depende de
01-perimetria-modelo-migracao

## Especificação funcional
- Uma constante `PERIMETRIA_SEGMENTOS` (lista ordenada de `(key, label)`) define os segmentos-padrão: pescoco/Pescoço, ombros/Ombros, peitoral/Peitoral, cintura/Cintura, abdomen/Abdómen, quadril/Quadril, coxa_d/Coxa D, coxa_e/Coxa E, panturrilha_d/Panturrilha D, panturrilha_e/Panturrilha E, braco_d_relaxado/Braço D (relaxado), braco_d_contraido/Braço D (contraído).
- `create_avaliacao` passa a aceitar `perimetria: dict[str, str] | None = None` (mapa `key -> valor cru`). Para cada segmento com valor preenchido, grava uma linha `Perimetria` ligada à avaliação, com `segmento = label` e `valor = Decimal`. Reusa `_parse_number` (aceita vírgula/ponto; recusa negativo; vazio → None → não grava linha).
- **Atomicidade**: toda a validação (antropométrica + perimetria) acontece ANTES de persistir; se qualquer valor de perimetria for inválido/negativo, levanta `ValidationError` e **nada** é gravado (nem a avaliação). A avaliação e as suas linhas de perimetria entram no mesmo `session_scope`.
- Segmento vazio não vira linha (nem zero — regra 6). Chaves fora de `PERIMETRIA_SEGMENTOS` são ignoradas.
- `list_perimetria(avaliacao_id) -> list[dict]` devolve as medidas da avaliação (`{segmento, valor}`) na ordem canónica dos segmentos-padrão. Leitura, sem log.
- Compatibilidade: `create_avaliacao` sem `perimetria` continua a funcionar igual (os testes existentes não quebram).

## Pré-condições
- Issue 01 concluída: modelo `Perimetria` e tabela existem. `create_avaliacao`, `_parse_number`, `session_scope` disponíveis. 180 testes verdes.

## Arquivos a criar
- `tests/test_perimetria_servico.py` — criar avaliação com 2 segmentos preenchidos → 2 linhas gravadas; segmento vazio → não grava linha; valor negativo num segmento → ValidationError e NADA gravado (a avaliação também não); valor com vírgula ("82,5") aceito e vira Decimal; `list_perimetria` devolve as medidas em ordem canónica; criar sem perimetria → 0 linhas e a avaliação criada na mesma.

## Arquivos a modificar
- `kairos/avaliacoes/service.py` —
  - importar `Perimetria` de `kairos.avaliacoes.models`.
  - adicionar a constante `PERIMETRIA_SEGMENTOS`.
  - estender `create_avaliacao` com o parâmetro `perimetria`: depois de parsear os campos antropométricos, parsear cada segmento via `_parse_number(valor, f"Perímetro {label}")`, montar a lista de `(label, Decimal)` dos não-vazios; dentro do `session_scope`, após `flush` da avaliação (para ter o id), adicionar as `Perimetria(avaliacao_id=..., segmento=label, valor=...)`. Manter o log de criação.
  - adicionar `list_perimetria(avaliacao_id)`: `select(Perimetria).where(...)`, devolver `{segmento, valor}` ordenado pela posição em `PERIMETRIA_SEGMENTOS` (ou por id, que é a ordem de inserção canónica).

## Camadas envolvidas
serviço, teste

## Status
concluída
