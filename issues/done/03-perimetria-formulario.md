# Secção de perimetria no formulário

## Descrição
Comportamento 1 (e o lado UI de 2-5): o formulário de nova avaliação ganha uma secção "Perimetria (cm)" com um campo por segmento-padrão; ao submeter, os valores preenchidos são passados ao serviço e gravados como linhas; erro de validação preserva os valores digitados.

## Depende de
02-perimetria-servico-guardar

## Especificação funcional
- `GET /alunos/{id}/avaliacoes/nova` mostra, além dos campos antropométricos, uma secção "Perimetria (cm)" com um campo por segmento-padrão (os 12 de `PERIMETRIA_SEGMENTOS`, na ordem canónica), cada um rotulado com o seu nome.
- `POST /alunos/{id}/avaliacoes` recolhe os valores de perimetria do formulário e passa-os ao serviço; os segmentos preenchidos são gravados como linhas da avaliação (issue 02 já faz o resto).
- Erro de validação (antropométrico ou de perimetria) → 400, re-renderiza o formulário com a mensagem e **preserva os valores digitados**, incluindo os de perimetria.
- Segmento vazio continua a não gravar linha (o serviço trata). id de aluno inexistente → 404.
- Casos de borda: número aceita vírgula ou ponto (serviço); a validação toda vem do serviço (thin client).

## Pré-condições
- Issue 02 concluída: `create_avaliacao(..., perimetria=...)`, `list_perimetria`, `PERIMETRIA_SEGMENTOS`. O formulário `nova.html` e a rota GET/POST existem (fatia 3). 187 testes verdes.

## Arquivos a criar
- `tests/test_perimetria_formulario.py` — GET nova mostra os 12 campos de segmento (name `perim_<key>`, ex.: `perim_cintura`) e o cabeçalho "Perimetria"; POST com data + perimetria (ex.: `perim_cintura=82,5`, `perim_coxa_d=58`) → 303 e `list_perimetria` da avaliação criada tem 2 medidas; POST com um segmento negativo (`perim_cintura=-5`) → 400, nada gravado (avaliação nem perimetria), e o valor "-5" preservado no campo; POST sem nenhuma perimetria → cria a avaliação com 0 medidas.

## Arquivos a modificar
- `kairos/avaliacoes/routes.py` —
  - `GET /alunos/{aluno_id}/avaliacoes/nova`: passar `segmentos=PERIMETRIA_SEGMENTOS` no contexto (importar do serviço).
  - `POST /alunos/{aluno_id}/avaliacoes`: obter os campos de perimetria com `form = await request.form()` e `perimetria = {key: form.get("perim_" + key) for key, _ in PERIMETRIA_SEGMENTOS}` (o `request` já é parâmetro; os `Form(None)` antropométricos continuam). Chamar `create_avaliacao(aluno_id, ..., perimetria=perimetria)`. Na `ValidationError`, re-renderizar com `segmentos=PERIMETRIA_SEGMENTOS` e `values` incluindo um sub-dict `perimetria` = os valores crus (`{key: form.get("perim_"+key)}`), para o template repor os campos.
- `kairos/templates/avaliacoes/nova.html` — antes do botão, acrescentar uma secção `<h3>Perimetria (cm)</h3>` e, para cada `(key, label)` em `segmentos`, um `<div class="field">` com `<label>{{ label }}</label>` e `<input type="number" step="0.1" inputmode="decimal" name="perim_{{ key }}" value="{{ (values.perimetria[key] if values and values.perimetria else '') or '' }}">`. Agrupar os campos de perimetria num contêiner para o CSS poder pô-los em grelha compacta.
- `kairos/static/css/components.css` — (opcional) uma grelha compacta para os campos de perimetria (ex.: `.perimetria-grid` com 2-3 colunas), só tokens; se não valer a pena, deixar em coluna simples.

## Camadas envolvidas
aplicação (rota GET/POST), frontend (nova.html + css), teste

## Status
concluída
