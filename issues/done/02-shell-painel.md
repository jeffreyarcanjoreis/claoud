# Shell do painel: topo e abas

## Descrição
Comportamentos 1, 2 e 3 do SPEC: o base.html passa a ter a barra do topo (marca + nome do coach) e a navegação por abas (Início, Avaliação Inicial, Alunos, Financeiro, Conteúdo & Comunicação); a aba da página atual aparece destacada; clicar numa aba leva à rota dela (links server-rendered, thin client).

## Depende de
01-tokens-base-fontes

## Especificação funcional
- Toda página que estende `base.html` mostra uma barra do topo: logo Kairos (SVG 2D inline, com o anel a girar por CSS) + wordmark "Kairos · painel do coach" + o nome do coach ("Jeffrey"), e, abaixo, a navegação por abas: **Início · Avaliação Inicial · Alunos · Financeiro · Conteúdo & Comunicação**.
- A aba correspondente ao caminho atual aparece destacada — calculada no template a partir de `request.url.path` (Início em `/`, Alunos em `/alunos` e sub-rotas, etc.). Nenhuma rota é alterada.
- Cada aba é um `<a href>` para a rota da área: Início `/`, Alunos `/alunos`, e as futuras `/avaliacao-inicial`, `/financeiro`, `/conteudo`. Navegação server-rendered (thin client).
- As abas de áreas ainda não construídas (Avaliação Inicial, Financeiro, Conteúdo & Comunicação) mostram um marcador discreto "em breve"; Início e Alunos não têm.
- O conteúdo de cada página passa a ser envolvido por um `<main class="content">` com a largura e o respiro da marca.
- Casos de borda: a barra e as abas aparecem em TODAS as páginas que usam base.html, incluindo o 404 (`nao_encontrado.html`) e os re-renders de erro dos formulários. Os links de áreas ainda não construídas apontam para rotas que só existem nas issues 05/06 — até lá, clicar dá 404 (esperado no meio da fatia). Isto NÃO quebra os testes existentes (que verificam texto/rotas de Alunos, não navegação nova).
- Sob `prefers-reduced-motion`, o anel do logo não roda (já garantido pela regra global da issue 01).

## Pré-condições
- Issue 01 concluída: `base.html` já carrega `tokens.css` e `base.css`; `/static` servido; `request` disponível no contexto dos templates (o `TemplateResponse` do projeto já passa `request`).

## Arquivos a criar
- `kairos/static/css/shell.css` — estilos da barra do topo, da navegação por abas (aba ativa + marcador "em breve"), do container `<main class="content">`, e as keyframes de rotação do anel do logo. Usa as custom properties de `tokens.css`.
- `tests/test_shell_painel.py` — verifica: (a) `GET /alunos` contém a barra do topo e os cinco rótulos de aba; (b) a aba "Alunos" está marcada como ativa em `/alunos` e a aba "Início" NÃO; (c) os `href` das abas apontam para `/`, `/alunos`, `/avaliacao-inicial`, `/financeiro`, `/conteudo`; (d) as abas futuras têm o marcador "em breve" e Alunos/Início não; (e) o `<link>` para `/static/css/shell.css` está presente; (f) a página 404 (`GET /alunos/999`) também mostra a barra e as abas.

## Arquivos a modificar
- `kairos/templates/base.html` — adicionar `<link rel="stylesheet" href="/static/css/shell.css">` no `<head>`; inserir, no início do `<body>`, o markup da barra do topo (logo SVG inline + wordmark + coach) e da navegação por abas; envolver `{% block content %}` num `<main class="content">`; calcular a aba ativa a partir de `request.url.path` (lógica de apresentação, no template). Não tocar em rotas nem nos templates de Alunos.

## Camadas envolvidas
frontend (CSS + template base), teste

## Status
concluída
