# 37 — Registro pós-treino (Fase 3 do roadmap da área do aluno)

Fase 3 de [docs/roadmap-area-aluno.md](../docs/roadmap-area-aluno.md). A válvula
**"o que mudou"**: o aluno registra como foi o treino (esforço percebido, sensação, o
que mudou, dor nova). Fecha o ciclo do dia e alimenta a leitura da próxima sessão
pelo coach.

## Status
concluída

> Escopo **enxuto** escolhido pelo PO: só o registro pós-sessão (RPE, sensação,
> o que mudou, dor nova). O log de carga/reps por série fica para a Fase 3b.

## Decisão de escopo (quero seu ok)
A spec (tela 02) lista duas coisas nesta frente:
1. **Registro pós-sessão** — RPE, como se sentiu, o que mudou, dor nova, "feito". ← esta fatia.
2. **Carga/reps feitas por série** (log por exercício) — mais granular, casa melhor com
   a **sessão guiada** (Fase 5). **Proponho deixar como Fase 3b**, depois da periodização.

Esta fatia entrega a válvula de maior valor (o "o que mudou → leitura da próxima")
sem depender do modelo de fases/níveis. Se você quiser o log de cargas por exercício
já agora, a gente amplia o escopo — é só dizer.

## Especificação funcional

### Modelo + migração
1. Tabela `registros_treino` (migração **0022**): `id`, `aluno_id` (FK alunos.id,
   index), `data` (Date), `treino_id` (FK treinos.id, **opcional** — qual treino fez),
   `rpe` (Integer 0–10 opcional — esforço percebido), `sensacao` (opção opcional),
   `o_que_mudou` (Text opcional), `dor_nova` (Text opcional), `created_at`. Vários por
   aluno (lista; não é único por dia — pode treinar mais de uma vez). Tipos portáveis;
   vazio = NULL (regra 6). A **existência** de um registro é o "feito".

### Serviço (`kairos/registro_treino/service.py`)
2. `SENSACAO_OPCOES = (pessima, ruim, ok, boa, otima)` + labels pt-BR.
3. `registrar(aluno_id, *, data=hoje, treino_id, rpe, sensacao, o_que_mudou, dor_nova)`
   — valida rpe 0–10, sensacao contra o conjunto, treino_id (se dado) **é do próprio
   aluno** (senão ValidationError); exige ao menos um campo de conteúdo (rpe/sensacao/
   o_que_mudou/dor_nova) preenchido. Cria o registro; loga.
4. `list_registros(aluno_id)` — do aluno, data desc (id desc desempate), com labels e
   o nome do treino (outer join). Read-only. `get_registro(id)` (dono checado na rota).

### Lado do aluno
5. Nova aba **Registro** na nav do aluno → `GET /aluno/registro`: um formulário
   "Como foi o treino?" (treino opcional dentre os do aluno, RPE 0–10, sensação, o que
   mudou, dor nova) + a **lista dos próprios registros** (histórico). `aluno_id` da
   **sessão**.
6. `POST /aluno/registro` → `registrar(...)` → 303 pra `/aluno/registro`. Erro →
   re-render com mensagem, sem perder o digitado.
7. No **home**, uma linha/CTA leve: se há treino de hoje e ainda não há registro hoje,
   "Como foi o treino de hoje? Registrar" → `/aluno/registro`. (Eco da regra de ouro.)

### Lado do coach
8. **Sem aba nova** (a ficha já tem muitas): a sub-aba **Acompanhamento** do coach
   ganha uma seção **"Registros do aluno"** listando os `list_registros(aluno_id)`
   (data, treino, RPE, sensação, o que mudou, dor nova) — read-only, abaixo das
   sessões realizadas que o coach anota. É a leitura da válvula pra ajustar a próxima.

### Geral
9. Isolamento: o aluno registra/vê só o próprio (aluno_id da sessão; treino_id
   validado como dele); o coach lê por aluno_id na URL. Escrita loga; textos pt-BR.
   Suíte anterior verde.

## Pré-condições
- Área do aluno (Fases 0–2) + treinos do aluno (existe). HEAD de migração: 0021.

## Arquivos a criar
- `kairos/registro_treino/__init__.py`, `models.py` (RegistroTreino), `service.py`,
  `routes.py` (aluno GET/POST).
- `migrations/versions/0022_create_registros_treino.py`.
- `kairos/templates/area_aluno/registro.html` (form + histórico do aluno).
- `tests/test_registro_treino.py`.

## Arquivos a modificar
- `kairos/main.py` — incluir o router.
- `kairos/templates/area_aluno/base.html` — item **Registro** na nav do aluno.
- `kairos/area_aluno/routes.py` — o CTA "registrar treino de hoje" no home
  (`GET /aluno`): flag `pode_registrar_hoje` (tem treino hoje e sem registro hoje).
- `kairos/templates/area_aluno/inicio.html` — a linha/CTA de registro.
- `kairos/acompanhamento/routes.py` (`GET /alunos/{id}/acompanhamento`) +
  `kairos/templates/acompanhamento/lista.html` — a seção "Registros do aluno"
  (importa `registro_treino.service.list_registros`).
- `kairos/static/css/area_aluno.css` — estilos do form/lista de registro.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): `RegistroTreino` + migração 0022.
- **serviço** (`servico-writer`): `registro_treino/service.py`.
- **aplicação** (`aplicacao-writer`): `registro_treino/routes.py`, CTA no home,
  seção na rota de acompanhamento do coach, include no `main.py`.
- **frontend** (`frontend-writer`): `registro.html` + CTA no home + nav + seção na
  `acompanhamento/lista.html`.
- **testes** (`teste-writer`): `tests/test_registro_treino.py` + suíte verde.

## Fora de escopo (Fase 3b / futuro)
- **Log de carga/reps feitas por exercício** (por série) — Fase 3b, junto da sessão
  guiada (Fase 5).
- Escolher regressão/progressão por exercício (depende dos 3 níveis — Fase 5).
- Marcar automaticamente a SessaoRealizada/presença do coach a partir do registro do
  aluno (por ora são coisas separadas; o coach anota o dele, o aluno o dele).
