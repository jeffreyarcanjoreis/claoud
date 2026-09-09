# 31 — Área do aluno: o próprio conteúdo, isolado (Fase 3.2 do épico de login)

Fatia 3.2 do épico [26-login-autenticacao.md](26-login-autenticacao.md). **Fecha o
épico.** Depende de [30-area-aluno-gate.md](done/30-area-aluno-gate.md) (o aluno já
entra em `/aluno`, com o `aluno_id` na sessão).

## Status
concluída

## Contexto
Na 3.1 a landing do aluno é só uma saudação. Aqui ela ganha o **conteúdo dele** —
próximos agendamentos, treinos atribuídos, avaliações e histórico — **só o dele**,
read-only. A camada de serviço já expõe tudo por `aluno_id` (`list_sessoes`,
`list_treinos`/`get_treino_detail`, `list_avaliacoes`/`get_avaliacao_detail`,
`list_sessoes_realizadas`), então esta fatia NÃO mexe em model/serviço/migração — só
adiciona rotas na área do aluno (reusando os serviços) + templates + testes.

## Princípio de isolamento (o coração da fatia)
- O `aluno_id` vem **SEMPRE da sessão** (`current_user(request)["aluno_id"]`),
  **NUNCA da URL**. As listagens usam esse id direto → isolamento automático.
- Nas rotas de **detalhe** (id do recurso na URL: treino, avaliação), o recurso é
  buscado e só é exibido se o `aluno_id` dele for **igual** ao da sessão; senão
  **404** (nunca 403 que confirmaria existência; nunca mostrar dado de outro aluno).
- A área do aluno é **read-only**: nenhuma rota de escrita sob `/aluno`.

## Especificação funcional

### Landing `/aluno` (agora com conteúdo)
1. Mantém a saudação "Olá, {primeiro nome}" da 3.1.
2. **Próximos agendamentos**: de `list_sessoes(aluno_id)`, só os com data **>= hoje**,
   em ordem cronológica; cada um mostra data, hora, tipo e, se houver treino
   associado, o nome do treino com link para a planilha dele (`/aluno/treinos/{id}`).
   Estado vazio honesto ("Nenhum agendamento próximo.").
3. **Meus treinos**: `list_treinos(aluno_id)` (nome + nº de exercícios), cada um com
   link "ver treino" → `/aluno/treinos/{treino_id}`. Estado vazio honesto.
4. **Minhas avaliações**: `list_avaliacoes(aluno_id)` (data), cada uma com link
   "ver" → `/aluno/avaliacoes/{avaliacao_id}`. Estado vazio honesto.
5. **Histórico de sessões**: `list_sessoes_realizadas(aluno_id)` (as últimas; data +
   presença + disposição se houver), read-only, sem detalhe próprio. Estado vazio
   honesto. (Se ficar pesado, mostrar só as N mais recentes — decidir na implementação;
   por ora listar todas em ordem decrescente.)
6. Se o `aluno_id` da sessão não resolver um Aluno (arquivado/removido), a página não
   quebra: saudação genérica + seções vazias.

### Detalhe do treino `/aluno/treinos/{treino_id}` (read-only, dono)
7. Mostra a **planilha** via `get_treino_detail(treino_id)` (nome, observação, itens
   com exercício/séries/reps/carga em ordem) — sem qualquer ação de editar/adicionar/
   remover/apagar (a versão do coach tem; a do aluno **não**).
8. **Verificação de dono**: `get_treino(treino_id)`; se None ou
   `treino["aluno_id"] != aluno_id da sessão` → **404**.

### Detalhe da avaliação `/aluno/avaliacoes/{avaliacao_id}` (read-only, dono)
9. Mostra o detalhe via `get_avaliacao_detail(avaliacao_id)` (antropometria + IMC/Δ
   calculados como já são, + perimetria) — read-only.
10. **Verificação de dono**: `get_avaliacao(avaliacao_id)`; se None ou
    `avaliacao["aluno_id"] != aluno_id da sessão` → **404**.

### Geral
11. Nenhuma rota nova aceita `aluno_id` pela URL/form; nenhum comportamento do coach
    muda; suíte anterior segue verde. Sem migração/model/serviço.

## Pré-condições
- Fatia 3.1 concluída (sessão do aluno com `aluno_id`; gate protege `/aluno*`).
- Serviços já existentes e keyed por aluno: `agenda.service.list_sessoes`;
  `treinos.service.list_treinos`/`get_treino`/`get_treino_detail`;
  `avaliacoes.service.list_avaliacoes`/`get_avaliacao`/`get_avaliacao_detail`;
  `acompanhamento.service.list_sessoes_realizadas`.

## Arquivos a criar
- `kairos/templates/area_aluno/base.html` — layout autônomo do aluno (extrai o
  esqueleto da `inicio.html` da 3.1: `#fundo3d`+scrim, `.cad-top` com wordmark +
  botão Sair `POST /logout`, `{% block content %}`, script `painel-fundo.js`).
- `kairos/templates/area_aluno/treino_detalhe.html` — planilha read-only (estende
  `base.html`).
- `kairos/templates/area_aluno/avaliacao_detalhe.html` — detalhe read-only (estende
  `base.html`).
- `tests/test_area_aluno_conteudo.py` — cobre itens 2–11, com ênfase no isolamento
  (aluno A não vê treino/avaliação do aluno B → 404; listagens só trazem o próprio).

## Arquivos a modificar
- `kairos/area_aluno/routes.py`:
  - `GET /aluno` passa a montar o contexto com as 4 seções (itens 2–5), reusando os
    `list_*` com o `aluno_id` da sessão; helpers de display locais (formatar data/
    hora, filtrar agendamentos futuros). Continua tolerante a `aluno_id` que não
    resolve (item 6).
  - `GET /aluno/treinos/{treino_id}` — dono + `get_treino_detail` (itens 7–8).
  - `GET /aluno/avaliacoes/{avaliacao_id}` — dono + `get_avaliacao_detail` (9–10).
  - Um helper `_aluno_id_da_sessao(request)` (lê `current_user`) e um
    `_negar_se_nao_dono(...)`/checagem inline que devolve `404` via
    `HTTPException`/`TemplateResponse` com status 404 no padrão do projeto.
- `kairos/templates/area_aluno/inicio.html` — refatorar para **estender**
  `area_aluno/base.html` e renderizar as 4 seções + estados vazios.

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): as 3 rotas de `area_aluno/routes.py`
  (landing com conteúdo + 2 detalhes com verificação de dono; aluno_id só da sessão).
- **frontend** (`frontend-writer`): `area_aluno/base.html` + refactor da
  `inicio.html` + `treino_detalhe.html` + `avaliacao_detalhe.html` (read-only, tokens
  da marca; sem ações de escrita).
- **testes** (`teste-writer`): `tests/test_area_aluno_conteudo.py` (isolamento é o
  foco) + suíte verde. (Mesma gotcha da 3.1: para simular aluno logado, dar
  monkeypatch em `kairos.area_aluno.routes.current_user` além do middleware.)

## Fora de escopo
- Aluno editar/registrar qualquer coisa (a área é só-leitura; feedback/registro do
  aluno é evolução futura).
- Gráfico de evolução na área do aluno (o `avaliacao_series` existe; fica pra depois).
- Vincular sessões realizadas a um detalhe próprio.
