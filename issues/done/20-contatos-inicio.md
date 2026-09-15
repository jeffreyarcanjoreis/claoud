# Issue 20 — Avaliação Inicial: central + acompanhamento de contatos no Início

## Status
concluída

## Contexto / decisão do PO
A **Avaliação Inicial** é a porta de entrada de todo novo interessado no trabalho
(Google Form → planilha de respostas no Drive). O PO decidiu:

1. **Fonte de verdade fica no Google.** As respostas — que incluem **dados de
   saúde sensíveis** (lesões, condições diagnosticadas, medicação) — moram só na
   planilha do Google. O app **não copia** esses dados.
2. O app oferece uma **central** que aponta pro Google (abrir a planilha de
   respostas, compartilhar o Form) + um **acompanhamento leve** dos contatos:
   apenas **nome + status** (a contatar / conversando / virou aluno), **sem
   nenhum dado de saúde**.
3. Isso vive **só no Início**, abrindo uma aba que expande na própria página,
   **igual às Tarefas** (tile clicável → seção abre embaixo, sem JS).
4. Os leads **saem do Financeiro**.

## NOTA — migração futura (deixar registrada no código)
Quando houver **hospedagem + login Google (OAuth/conta de serviço) + postura de
consentimento/RGPD**, evoluir para uma **integração autenticada** que lê as
respostas direto da planilha (padrão espelhado da Agenda `gcal.py`, porém
autenticado por serem dados sensíveis — nunca via link público/CSV). Aí o
acompanhamento pode ser alimentado automaticamente pelas respostas, em vez de
manual. Registrar essa nota no docstring do módulo `kairos/contatos/` e no doc
`10 - Workflow da Área do Coach`.

## Escopo desta fatia
- Acompanhamento **manual e leve** de contatos no Início (nome + status), sem
  dados de saúde.
- Central com links pro Google (planilha de respostas + Form) — via config, com
  estado de configuração honesto quando faltarem.
- Espelha o padrão Tarefas (tile com contagem → seção expansível).
- Tirar os leads do Financeiro.
- `/avaliacao-inicial` passa a redirecionar para `/` (Início).

## Fora de escopo (futuro — ver nota acima)
- Ler as respostas do Google dentro do app (integração autenticada).
- Converter um contato em Aluno completo com 1 clique.

## Modelo de dados
Novo módulo isolado `kairos/contatos/` (regra 1). **Só tipos portáveis** (regra 4);
campo vazio = NULL (regra 6). **Nenhum campo de saúde** — decisão de privacidade.

Modelo `Contato` (tabela `contatos`):
- `id` PK
- `nome` — obrigatório (String 200)
- `contato` — opcional (String 200) — telefone/@/e-mail, texto livre (dado de
  contato, não de saúde)
- `status` — obrigatório, um de `STATUS_VALIDOS` = (`a_contatar`, `conversando`,
  `virou_aluno`, `sem_interesse`); default `a_contatar`
- `observacao` — opcional (texto)
- `created_at` — server_default now()

Migração `0015_create_contatos` (head atual 0014 → nova head 0015).

## Serviço `kairos/contatos/service.py` (espelha `tarefas/service.py`)
- `ValidationError` (pt-BR).
- `STATUS_VALIDOS` + rótulos pt-BR.
- `create_contato(*, nome, contato, observacao)` — status nasce `a_contatar`.
- `list_contatos_abertos()` — status em (`a_contatar`, `conversando`),
  mais recentes primeiro (`created_at desc`, id desc).
- `get_contato(id)`.
- `atualizar_status(id, status)` — valida o status; ao marcar `virou_aluno`/
  `sem_interesse` o contato sai da lista de abertos.
- `remover_contato(id)`.

## Config (`kairos/config.py`, espelhando `gcal_ics_url`)
- `avaliacao_form_url()` — lê `KAIROS_AVALIACAO_FORM_URL` (link público do Form
  pra compartilhar com o interessado).
- `avaliacao_respostas_url()` — lê `KAIROS_AVALIACAO_RESPOSTAS_URL` (planilha de
  respostas). Ambos opcionais → `None` mostra estado "configure aqui" (rule 6),
  nunca link inventado.

## Rotas `kairos/contatos/routes.py` (espelha `tarefas/routes.py`)
- `POST /contatos` — cria; em erro re-renderiza `painel/inicio.html` com a seção
  aberta e a mensagem.
- `POST /contatos/{id}/status` — atualiza status (Form `status`).
- `POST /contatos/{id}/remover`.
Todas terminam em `RedirectResponse("/")` (303). Registrar `contatos_router` em
`main.py`.

## Início (`painel/routes.py` + `painel/inicio.html`)
- `inicio_context(...)` monta também: `contatos` (formatados: rótulo de status
  pt-BR), `contato_error`, `contato_values`, e os dois links (`form_url`,
  `respostas_url`) pra central.
- No `inicio.html`:
  - o tile atual **"Novos contatos"** (hoje `<a href="/financeiro">` com selo "em
    breve") vira um **`<label class="stat stat-toggle">`** ligado a um segundo
    checkbox `#contatos-toggle`, mostrando a contagem real;
  - nova seção `.contatos` (recolhida; abre com o toggle) com: (a) a **central** —
    botões "Abrir respostas (Google)" e "Compartilhar o Form", ou o estado de
    configuração quando faltar a URL; (b) form de adicionar contato (nome +
    contato + observação); (c) lista dos contatos em aberto, cada um com um
    seletor de status (a contatar / conversando / virou aluno / sem interesse) +
    "remover".

## Financeiro
- Remover do `templates/painel/financeiro.html` a caixa `.coming-soon` de "Novos
  contatos (leads)" (o épico Financeiro está completo; nada mais "por vir" ali).

## `/avaliacao-inicial`
- Em `painel/routes.py`, o redirect 307 passa de `/financeiro` para `/`.

## CSS (`components.css`)
- Espelhar o toggle das tarefas pros contatos (dois toggles convivem: os dois
  checkboxes antes de `.stats`; `.contatos` escondida e
  `#contatos-toggle:checked ~ .contatos { display: block }`). Reusar
  `.card-list`/`.card`/`.button-link`. Sem cores novas.

## Testes (teste-writer, espelhando os das tarefas)
- `test_contato_model` (fixa a head 0015; cria/lê; garante que NÃO há coluna de
  saúde).
- Serviço: criar (nome obrigatório; vazios viram NULL; status nasce `a_contatar`);
  listar abertos (ordem; exclui `virou_aluno`/`sem_interesse`); atualizar status
  (inválido rejeitado); remover.
- Rotas: POST cria e redireciona; erro re-renderiza o Início; status/remover;
  404 em id inexistente.
- Início: o tile "Novos contatos" mostra a contagem e abre a seção; a central
  mostra o estado de configuração quando as URLs faltam.
- Financeiro: `/financeiro` **não** menciona mais "Novos contatos (leads)".
- `/avaliacao-inicial` redireciona para `/` (ajustar o teste em
  `test_areas_em_breve.py`).

## Camadas / subagentes
configuracao-writer (as 2 URLs no config) → banco-migracao-writer (modelo + 0015)
→ servico-writer (service) → aplicacao-writer (routes + inicio_context + redirect
+ registro no main) → frontend-writer (inicio.html + financeiro.html + CSS) →
teste-writer (suíte).
