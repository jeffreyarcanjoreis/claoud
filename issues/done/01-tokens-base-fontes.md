# Tokens, base e fontes da marca

## Descrição
Comportamentos 9, 10 e 12 do SPEC: criar `static/css/tokens.css` (paleta, tipografia, espaçamento, easing como custom properties) e `base.css` (reset + corpo escuro + tipografia base), servidos pelo FastAPI e carregados no base.html; as fontes Fraunces e Archivo são self-hosted (sem CDN externo); com `prefers-reduced-motion` nenhuma transição não-essencial é aplicada. É a fundação visual que toda tela herda.

## Depende de
nenhuma

## Especificação funcional
- O FastAPI serve arquivos estáticos em `/static/...` (um arquivo existente responde 200; inexistente responde 404 sem quebrar a app).
- `/static/css/tokens.css` e `/static/css/base.css` existem e respondem 200.
- Toda página que estende `base.html` carrega esses dois CSS no `<head>`.
- As fontes Fraunces e Archivo são servidas de `/static/fonts/` (self-hosted). Renderizar qualquer página NÃO referencia nenhum domínio externo (nada de `fonts.googleapis.com`/`gstatic`).
- `tokens.css` define custom properties reutilizáveis: paleta (`--void #14130f`, `--bone #f0ebe0`, `--bone-dim #d4cdbd`, `--clay #c2613f`, `--sage #6b7355`, `--gold #c89b4a`, `--line`), famílias (`--font-serif: Fraunces`, `--font-sans: Archivo`), escala tipográfica, espaçamento, easing (`--ease: cubic-bezier(.2,.8,.2,1)`), raios.
- `base.css`: `@font-face` self-hosted; reset; `body` com fundo `--void` e texto `--bone` em Archivo; títulos (h1/h2) em Fraunces; links; e legibilidade base dos elementos de formulário (input/textarea/select/button/label) sobre o fundo escuro — o suficiente para os formulários de Alunos continuarem usáveis.
- Regra global `@media (prefers-reduced-motion: reduce)` que anula transições e animações não-essenciais.
- Caso de borda intermediário: entre esta issue e a 03, os componentes de Alunos (cartão, selo, mensagens) ficam sem o polimento de marca — isso é esperado; o texto das telas não muda, então os testes existentes continuam verdes. O look completo dos componentes é a issue 03.

## Pré-condições
- Fatia 1 concluída; `kairos/main.py` cria o app FastAPI; 67 testes verdes.
- Rede disponível na execução para baixar os woff2 (com fallback documentado).

## Arquivos a criar
- `kairos/static/css/tokens.css` — as custom properties da marca.
- `kairos/static/css/base.css` — `@font-face`, reset, body escuro, tipografia base, links, base de formulário, `prefers-reduced-motion`.
- `kairos/static/fonts/` — os woff2 de Fraunces (300/400/500 + itálico 300/400) e Archivo (300/400/500/600). Método: obter via Google Fonts CSS API (UA de navegador moderno → extrair URLs woff2 → baixar). Fallback se a rede falhar: registrar no resumo e deixar os `@font-face` prontos apontando para os arquivos, caindo para stack de sistema (`Georgia, serif` / `system-ui, sans-serif`) até os arquivos existirem.
- `tests/test_frontend_base.py` — verifica: (a) `GET /static/css/tokens.css` e `.../base.css` → 200; (b) uma página que usa base.html (ex. `GET /alunos`) contém os dois `<link rel="stylesheet">` para `/static/css/...`; (c) essa página não contém `fonts.googleapis.com` nem `gstatic`.

## Arquivos a modificar
- `kairos/main.py` — montar `StaticFiles` em `/static` a partir de `kairos/static` (caminho derivado de `__file__`, não do cwd).
- `kairos/templates/base.html` — no `<head>`: remover o `<style>` inline atual e adicionar `<link rel="stylesheet" href="/static/css/tokens.css">` e `.../base.css`. Definir também o `<title>` e `lang` como já estão. (Os estilos de componentes que hoje vivem inline passam a ser responsabilidade da issue 03.)
- `pyproject.toml` — incluir `kairos/static/**/*` no `package-data` (hoje só inclui `templates/**/*.html`).

## Camadas envolvidas
frontend (CSS/estáticos/fontes), aplicação (mount de estáticos em main.py), teste

## Status
concluída
