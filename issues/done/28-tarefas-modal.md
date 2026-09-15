# Issue 28 — Tarefas em pop-up (modal) no Início

## Status
concluída

## Contexto / decisão do PO
Aplicar às Tarefas do Início o mesmo tratamento de pop-up do cadastro: clicar no
tile "Tarefas" abre um **modal** central (lista + adicionar), em vez de expandir a
lista empurrando o conteúdo pra baixo. Reusar o modal refinado da issue 27
(cabeçalho fixo com kicker + título, corpo rolável com barra fina, ×, fecha em
×/Esc/backdrop).

## Escopo (recomendado: modal fluido por AJAX)
- Tile "Tarefas" → abre o modal com o formulário de adicionar + a lista das tarefas
  abertas (cada uma com Concluir / remover).
- **Ações por AJAX, sem recarregar:** adicionar, concluir e remover acontecem via
  fetch; a lista dentro do modal e a contagem no tile atualizam na hora (o modal
  permanece aberto).
- **Progressive enhancement / fallback sem JS:** hoje o tile é um toggle nativo
  (checkbox) que expande a `.tarefas` embaixo. Sem JS isso continua funcionando
  (expande inline) e os forms fazem POST normal (redirect pra `/`). Com JS, o clique
  é interceptado e o conteúdo abre no modal, e os forms enviam por AJAX.

> Alternativa mais leve (se preferir): o modal abre, mas cada ação (adicionar/
> concluir/remover) recarrega a página (modal fecha, Início mostra a lista nova).
> Bem menos JS. **Recomendo a versão fluida** pra ficar realmente bonito.

## Reaproveitamento — shell de modal compartilhado
Extrair o visual do modal (hoje só na vitrine, `.v-modal*` em `vitrine.css`) para um
CSS compartilhado `static/css/modal.css`, carregado por `base.html` (painel),
`vitrine/hero.html` e `contatos/cadastro.html`. A vitrine passa a usar esse arquivo
(remove a duplicação). Assim o modal das Tarefas e o do cadastro compartilham a
mesma aparência e o mesmo comportamento.

## Camadas
- **frontend**:
  - `static/css/modal.css` (novo): as classes `.v-modal*` movidas/refinadas da
    vitrine, genéricas (servem painel e vitrine). `base.html`/`hero.html`/
    `cadastro.html` carregam-no (com `?v={{ asset_ver }}`).
  - `painel/inicio.html`: envolver o conteúdo das Tarefas num modal (`.v-modal` com
    header "Organização / Tarefas" + corpo com o form + a lista). Manter o
    `#tarefas-toggle` e a `.tarefas` como fallback sem JS (o JS esconde o inline e
    usa o modal). O tile "Tarefas" ganha `data-abre-tarefas`.
  - `static/js/painel-tarefas.js` (novo, ou estender um JS do painel): abre/fecha o
    modal; intercepta os submits (adicionar/concluir/remover) → fetch; ao ok,
    atualiza a lista e a contagem do tile. Reusa um helper de modal comum
    (`static/js/modal.js`) compartilhado com a vitrine, se compensar.
- **aplicação** (`tarefas/routes.py`): content-negotiation (como no `/comecar`):
  - `POST /tarefas`, `POST /tarefas/{id}/concluir`, `POST /tarefas/{id}/remover`
    respondem **JSON** quando o pedido é AJAX; o caminho HTML/redirect atual fica
    intacto (fallback).
  - Um jeito de o JS obter a lista atualizada: uma rota `GET /tarefas/fragmento`
    (HTMLResponse) que renderiza só o partial da lista de tarefas abertas, pro JS
    trocar o innerHTML — mantém a marcação server-side (DRY). (Extrair a lista pra um
    partial `painel/_tarefas_lista.html` reusado pelo Início e pelo fragmento.)
  - `inicio_context`/serviço não mudam de regra — só a apresentação.

## Testes
- `POST /tarefas` (e concluir/remover) com `Accept: application/json` → JSON `{ok:..}`;
  sem o header → segue redirecionando pra `/` (fallback intacto — testes atuais valem).
- `GET /tarefas/fragmento` → 200, contém as tarefas abertas (e não o shell inteiro).
- `GET /` (Início) contém o modal de tarefas (`data-abre-tarefas`, `.v-modal`) e ainda
  a `.tarefas` de fallback.
- Suíte inteira verde. Sem migração.

## Fora de escopo
- Mudar a regra das tarefas (categorias, prazo, "atrasada") — só a apresentação.

## Camadas / subagentes
aplicacao-writer (content-negotiation nas rotas de tarefa + rota do fragmento) →
frontend-writer (extrair modal.css compartilhado; modal no Início; partial da lista;
JS de abrir/fechar + AJAX; carregar modal.css na vitrine/cadastro/base) →
teste-writer (JSON, fragmento, presença do modal; suíte).
