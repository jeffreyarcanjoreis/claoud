# Serviço de avaliação

## Descrição
Comportamentos 4, 5, 6, 7 (lado da regra): criar avaliação com validação (data obrigatória; números válidos e não-negativos; vazio vira NULL), listar as avaliações de um aluno em ordem cronológica inversa, e obter uma avaliação. Toda a regra no serviço (fat server).

## Depende de
01-avaliacao-modelo-migracao

## Especificação funcional
- `create_avaliacao(aluno_id, *, data, peso, altura, gordura_pct, massa_magra, massa_gorda)` recebe valores crus (strings ou None) e:
  - **data obrigatória**: ISO "YYYY-MM-DD"; ausente ou inválida → `ValidationError` com mensagem clara ("Data é obrigatória." / "Data inválida."), nada gravado.
  - **métricas**: número decimal; vazio → None (NULL, regra 6). Aceita vírgula ou ponto ("72,5" e "72.5"). Inválido (não-numérico) → `ValidationError` por campo ("Peso inválido." etc.). Negativo → `ValidationError` ("Peso não pode ser negativo." etc.).
  - grava via `session_scope`, loga a criação (id + aluno_id), retorna o dict de primitivos.
- `list_avaliacoes(aluno_id) -> list[dict]`: as avaliações do aluno em **ordem cronológica inversa** (data desc; desempate por id desc). Operação de leitura.
- `get_avaliacao(avaliacao_id) -> dict | None`: uma avaliação, ou None se não existe.
- Casos de borda: métrica "0" é válida (não é vazio nem negativo); a existência do aluno é garantida pela rota (que faz 404), não pelo serviço.
- Δ e IMC NÃO entram aqui — são a issue 05.

## Pré-condições
- Issue 01 concluída: modelo `Avaliacao` e tabela existem. Padrão do serviço de alunos disponível como referência.

## Arquivos a criar
- `kairos/avaliacoes/service.py` — no estilo de `kairos/alunos/service.py`:
  - `class ValidationError(Exception)` própria do módulo (mensagem em português).
  - helper `_parse_number(value, field_label) -> Optional[Decimal]`: normaliza (strip; vazio→None), troca vírgula por ponto, converte para `Decimal`; inválido → ValidationError(f"{field_label} inválido."); negativo → ValidationError(f"{field_label} não pode ser negativo.").
  - reutiliza a ideia de `_parse_date` (data obrigatória: se None após parse → ValidationError("Data é obrigatória.")).
  - `_to_dict(avaliacao)` com id, aluno_id, data, peso, altura, gordura_pct, massa_magra, massa_gorda, created_at (primitivos/Decimal, extraídos dentro da sessão).
  - `create_avaliacao(...)`, `list_avaliacoes(aluno_id)`, `get_avaliacao(avaliacao_id)`.
- `tests/test_avaliacao_servico.py` — criar válido grava e volta; sem data → ValidationError e nada gravado; número inválido → ValidationError; número negativo → ValidationError; métrica vazia vira None; "0" é aceito; list em ordem data desc (cria 3 datas fora de ordem, confere a ordem); get de id inexistente → None.

## Arquivos a modificar
- Nenhum (módulo novo; o serviço é autocontido). `list_avaliacoes`/`create_avaliacao` serão consumidos pelas rotas nas issues 03-05.

## Camadas envolvidas
serviço, teste

## Status
concluída
