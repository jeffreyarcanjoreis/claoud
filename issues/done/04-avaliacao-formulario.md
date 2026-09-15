# Formulário de nova avaliação

## Descrição
Comportamentos 4, 5, 6, 7 (lado da UI): formulário para registar uma avaliação do aluno; ao submeter válido, a avaliação passa a aparecer na lista; sem data ou com número inválido/negativo, recusa com mensagem clara e não grava; campo numérico vazio grava NULL.

## Depende de
03-avaliacoes-subaba-lista

## Especificação funcional
- `GET /alunos/{id}/avaliacoes/nova` mostra o formulário de nova avaliação (dentro da ficha, sub-aba Avaliações ativa): campos data, peso, altura, % gordura, massa magra, massa gorda.
- `POST /alunos/{id}/avaliacoes` com dados válidos cria a avaliação e redireciona (303) para `/alunos/{id}/avaliacoes`; a nova avaliação passa a aparecer na lista.
- Sem data, ou com número inválido/negativo → 400, re-renderiza o formulário com a mensagem do serviço e os valores digitados preservados; nada gravado.
- Campo numérico vazio é gravado como NULL.
- id de aluno inexistente (GET ou POST) → 404.
- Casos de borda: número aceita vírgula ou ponto (o serviço já trata); a validação toda vem do serviço (thin client).

## Pré-condições
- Issue 03 concluída: `ficha_layout.html`, `avaliacoes/routes.py`, `create_avaliacao` no serviço, o botão "Registar avaliação" na lista.

## Arquivos a criar
- `kairos/templates/avaliacoes/nova.html` — `{% extends "alunos/ficha_layout.html" %}`; no bloco: formulário `method="post" action="/alunos/{id}/avaliacoes"` com os 6 campos (data = `<input type="date">`; métricas = `<input type="number" step="0.01">` aceitando também vírgula), exibição de `error` e valores preservados (`values`), botão "Guardar avaliação". Reusa o visual de formulário de components.css.
- `tests/test_avaliacao_formulario.py` — GET nova → 200 com o form; POST válido → 303 para a lista e a avaliação aparece; POST sem data → 400 e nada gravado, valores preservados; POST número negativo/inválido → 400; campo vazio → NULL; `/alunos/999/avaliacoes/nova` → 404; POST em aluno inexistente → 404.

## Arquivos a modificar
- `kairos/avaliacoes/routes.py` — adicionar `GET /alunos/{aluno_id}/avaliacoes/nova` (get_aluno→404; renderiza nova.html com header + subtab) e `POST /alunos/{aluno_id}/avaliacoes` (get_aluno→404; recebe os campos via `Form`; chama `create_avaliacao(aluno_id, ...)`; `ValidationError` → re-render 400 com `error`/`values`; sucesso → RedirectResponse 303 para a lista). ATENÇÃO à ordem: registar `/avaliacoes/nova` (literal) ANTES de `/avaliacoes/{avaliacao_id}` (a rota de detalhe da issue 05), e `avaliacao_id` tipado int.
- `kairos/static/css/components.css` — só se precisar de ajuste (o padrão de formulário já existe).

## Camadas envolvidas
aplicação (rotas GET/POST de avaliacoes), frontend (nova.html), teste

## Status
concluída
