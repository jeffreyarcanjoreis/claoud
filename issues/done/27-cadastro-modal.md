# Issue 27 — Avaliação Inicial em modal (pop-up) na vitrine

## Status
concluída

## Contexto / decisão do PO
Para ficar mais bonito, a Avaliação Inicial (o cadastro) deve abrir num **modal
(pop-up)** sobre a vitrine, em vez de navegar para a página `/comecar`. A página
`/comecar` continua existindo como **fallback** (sem JS, e para o link
"Compartilhar o cadastro" do painel).

## Escopo
- Na vitrine (`/vitrine`), os gatilhos "Começar" abrem um modal com o formulário do
  cadastro, sem sair da página.
- Envio via **fetch (AJAX)**: em caso de sucesso, o modal mostra "Recebido!" ali
  mesmo; em erro de validação, mostra a mensagem no modal — sem recarregar.
- **Progressive enhancement**: os gatilhos continuam sendo `<a href="/comecar">`;
  o JS intercepta o clique pra abrir o modal. Sem JS, o link leva pra `/comecar`
  (a página atual, intacta).
- Acessível: `role="dialog"`, `aria-modal`, fecha no backdrop / Esc / botão ×,
  foco vai pro modal ao abrir e volta ao gatilho ao fechar.

## Backend (mudança pequena, com fallback)
- `POST /comecar` ganha **content-negotiation**: se a requisição pede JSON
  (`Accept: application/json` ou header `X-Requested-With`), responde
  `JSONResponse`:
  - sucesso → `{"ok": true}` (200);
  - `ValidationError` → `{"ok": false, "error": "<mensagem>"}` (400).
  O caminho HTML atual (página `/comecar` com `enviado`/`error`) fica **inalterado**
  para o fallback sem JS. Nenhuma regra de negócio muda — só o formato da resposta
  quando é AJAX.

## Frontend
- **Partial compartilhado** `templates/contatos/_cadastro_campos.html`: os campos do
  formulário (nome, contato, idade, sexo, objetivos, saúde, consentimento). Passa a
  ser incluído por (a) `contatos/cadastro.html` (refactor — mesmo resultado visual) e
  (b) o modal da vitrine. Evita duplicar o formulário em dois lugares.
- `vitrine/hero.html`: adicionar o modal (`<div class="v-modal" hidden>` com backdrop
  + card contendo o `<form action="/comecar" method="post">` que inclui o partial +
  um estado de sucesso oculto). Os CTAs "Começar" (topo e seção "Vamos começar")
  ganham `data-abre-cadastro` (continuam com `href="/comecar"` como fallback).
- `vitrine/routes.py`: passar as listas de opções (`_cadastro_opcoes_context()` do
  módulo contatos, ou equivalente) no contexto da vitrine, pros selects do modal.
- `static/js/vitrine-hero.js`: abrir/fechar o modal (clique nos gatilhos, backdrop,
  Esc, ×, foco), e interceptar o submit → `fetch('/comecar', {headers: Accept json})`
  → mostra sucesso/erro no modal; se o fetch falhar (rede), deixa o form submeter
  normal (fallback).
- `static/css/vitrine.css`: estilos do modal (backdrop escurecido, card centrado no
  visual da marca, scroll interno em telas pequenas, responsivo). Reusar tokens; sem
  cores novas.

## Testes
- `POST /comecar` com `Accept: application/json`: sucesso → JSON `{"ok": true}`;
  sem consentimento → JSON `{"ok": false, "error": ...}` 400. (Serviço inalterado.)
- `POST /comecar` sem Accept json (fallback) → continua renderizando HTML
  (`enviado`/`error`) como hoje — os testes existentes seguem válidos.
- `GET /vitrine`: contém o modal (`class="v-modal"`) e o formulário do cadastro
  (campos nome/contato/consentimento), e os CTAs têm `data-abre-cadastro`.
- `GET /comecar`: continua 200 e mostrando o formulário (via o partial).
- Rodar a suíte inteira; verde. Sem migração.

## Fora de escopo
- Mudar o cadastro em si (campos, validação) — só a apresentação (modal + AJAX).

## Camadas / subagentes
aplicacao-writer (JSON no POST /comecar + contexto de opções na rota da vitrine) →
frontend-writer (partial + modal no hero + JS + CSS + refactor do cadastro.html) →
teste-writer (JSON, modal, fallback; suíte).
