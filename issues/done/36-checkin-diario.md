# 36 — Check-in diário (Fase 2 do roadmap da área do aluno)

Fase 2 de [docs/roadmap-area-aluno.md](../docs/roadmap-area-aluno.md). A **válvula-
assinatura** do método: o aluno registra como chegou hoje (sono, estresse, energia,
humor, dor) e isso vira leitura pro coach. É a válvula nº 1 das cinco.

## Status
concluída

## Regra de ouro (spec)
"Todo input do aluno tem que mudar algo visível. Sem eco, o check-in vira formulário
morto." Nesta fatia o eco é **honesto**, sem fingir automação:
- ao registrar, o home confirma o check-in de hoje e mostra o **treino de hoje** junto;
- o **coach lê** o check-in (é o que fecha o laço — ele ajusta pela conversa/treino).
A **reconfiguração automática** do treino pelo check-in depende da periodização
(Fase 5) e **fica fora** desta fatia — não vamos simular um ajuste que o sistema
ainda não sabe fazer (regra 6).

## Modelo de "editável até o fim do dia"
Um check-in por aluno por dia (UNIQUE aluno_id+data). Enviar de novo **no mesmo dia**
atualiza (upsert), como `set_plano`/`registrar_pagamento` já fazem. Dias passados são
só leitura (o formulário é sempre do **hoje**).

## Especificação funcional

### Modelo + migração
1. Tabela `checkins` (migração **0021**): `id`, `aluno_id` (FK alunos.id, index),
   `data` (Date), `sono_horas` (Numeric(3,1) opcional), `sono_qualidade` (opção
   opcional), `estresse` (Integer 0–10 opcional), `energia` (Integer 0–10 opcional),
   `humor` (opção opcional), `dor_local` (texto opcional), `dor_intensidade` (Integer
   0–10 opcional), `observacao` (texto opcional), `created_at`. **UNIQUE(aluno_id,
   data)**. Tipos portáveis (regra 4). Campo sem dado = NULL (regra 6).

### Serviço (`kairos/checkin/service.py`)
2. Opções fixas (vocabulário controlado, com labels pt-BR):
   `QUALIDADE_SONO = (ruim, regular, boa, otima)`;
   `HUMOR = (muito_baixo, baixo, neutro, bom, otimo)`.
3. `registrar_checkin(aluno_id, data, **campos)` — **UPSERT** por (aluno_id, data):
   valida escalas 0–10 (estresse/energia/dor_intensidade), sono_horas 0–24,
   opções contra os conjuntos fixos; exige **ao menos um campo preenchido** (senão
   `ValidationError` "Preencha ao menos um campo do check-in."); vazios → NULL. Loga.
4. `checkin_de_hoje(aluno_id)` / `get_checkin(aluno_id, data)` — o check-in do dia (ou
   None). `list_checkins(aluno_id)` — histórico (data desc), pro coach e pra evolução.
   Todos read-only, sem log. Helpers de label pt-BR nos dicts.

### Lado do aluno
5. `GET /aluno/checkin` — formulário do **check-in de hoje**; se já existe hoje, vem
   **pré-preenchido** (edição). Campos: sono (horas + qualidade), estresse (0–10),
   energia (0–10), humor, dor (local + intensidade), observação.
6. `POST /aluno/checkin` (aluno_id da **sessão**) — `registrar_checkin(...)` pro
   **hoje**; sucesso → 303 pro `/aluno` (home). Erro de validação → re-render com
   mensagem, sem perder o que foi digitado.
7. No **home** (`/aluno`), o card **"Check-in de hoje"**: se ainda não fez hoje, um
   CTA "Fazer check-in" → `/aluno/checkin`; se já fez, um resumo (os valores de hoje)
   + "editar até o fim do dia". Logo abaixo/junto, o **treino de hoje** (a sessão de
   hoje, se houver) — o eco honesto de que o check-in e o dia estão ligados.

### Lado do coach
8. Nova sub-aba **Check-ins** na ficha do aluno (`GET /alunos/{id}/checkins`): lista os
   check-ins do aluno (mais recentes primeiro) com os valores do dia — o coach lê o
   estado pra ajustar. 404 se o aluno não existe. Read-only (o coach não registra
   check-in por ninguém).

### Geral
9. Isolamento: o aluno registra/vê só o **próprio** check-in (aluno_id da sessão,
   nunca da URL); o coach lê por aluno_id na URL. Escrita loga (regra 8); textos
   pt-BR (regra 10). Suíte anterior segue verde.

## Pré-condições
- Área do aluno com nav (Fases 0/1) e gate por papel. HEAD de migração: 0020.

## Arquivos a criar
- `kairos/checkin/__init__.py`, `kairos/checkin/models.py` (CheckinDiario),
  `kairos/checkin/service.py`, `kairos/checkin/routes.py` (aluno GET/POST + coach GET).
- `migrations/versions/0021_create_checkins.py`.
- `kairos/templates/area_aluno/checkin.html` (formulário do dia).
- `kairos/templates/checkin/ficha_checkins.html` (lista pro coach, estende
  `alunos/ficha_layout.html`).
- `tests/test_checkin.py` (serviço upsert/validação + rotas dos dois lados +
  isolamento + card do home + editável-no-mesmo-dia).

## Arquivos a modificar
- `kairos/main.py` — incluir o `checkin.routes` router.
- `kairos/area_aluno/routes.py` — `GET /aluno` injeta `checkin_hoje` (resumo ou None)
  e o `treino_hoje` (sessão de hoje, se houver).
- `kairos/templates/area_aluno/inicio.html` — card "Check-in de hoje" + treino de hoje.
- `kairos/templates/area_aluno/base.html` — (opcional) item na nav pro check-in, ou
  só via o card do home; decidir na execução (o card já é o acesso principal).
- `kairos/templates/alunos/ficha_layout.html` — sub-aba **Check-ins**.
- `kairos/static/css/area_aluno.css` — estilos do card/formulário do check-in
  (escalas, opções); só tokens da marca.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): `CheckinDiario` + migração 0021.
- **serviço** (`servico-writer`): `checkin/service.py` (upsert + validação + labels).
- **aplicação** (`aplicacao-writer`): `checkin/routes.py` (aluno + coach), card do
  home + treino de hoje, include no `main.py`.
- **frontend** (`frontend-writer`): `checkin.html` (aluno) + `ficha_checkins.html`
  (coach) + card no home + sub-aba na ficha.
- **testes** (`teste-writer`): `tests/test_checkin.py` + suíte verde.

## Fora de escopo (fases/futuro)
- **Reconfiguração automática do treino** pelo check-in (depende da periodização —
  Fase 5). Aqui: registrar + coach lê + eco honesto no home.
- Mapa corporal clicável (v1 usa local em texto + intensidade); tendências/gráfico do
  check-in ao longo do tempo; Pulso Kairos (Fase 4).
