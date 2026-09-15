# 38 — Autoavaliações (Fase 4c do roadmap da área do aluno)

Sub-fatia 4c de [docs/roadmap-area-aluno.md](../docs/roadmap-area-aluno.md). A
**válvula nº 4**: o coach envia um questionário de percepção; o aluno responde; o
coach lê. Percepção subjetiva que alimenta a leitura do coach (a "Ficha F" da spec).

## Status
planejada

## Escopo (pragmático)
- O coach **cria** uma autoavaliação (título + algumas perguntas), enviada a **um
  aluno**. Cada pergunta tem tipo **escala (0–10)** ou **texto**.
- O aluno vê as **pendentes** e **respondidas**, responde as pendentes (uma vez →
  vira respondida, depois read-only).
- Sem editor de questionário reutilizável/templates (v1): a criação é um formulário
  simples com N linhas de pergunta (as vazias são ignoradas). Templates ficam pra
  futuro.

## Especificação funcional

### Modelos + migração
1. `autoavaliacoes` (migração **0023**): `id`, `aluno_id` (FK alunos.id, index),
   `titulo` (String), `status` ("pendente"|"respondida", default "pendente"),
   `created_at` (enviada em), `respondida_em` (DateTime, nullable).
2. `autoavaliacao_perguntas` (mesma migração): `id`, `autoavaliacao_id` (FK, index),
   `ordem` (Integer), `texto` (Text), `tipo` (String: "escala"|"texto"), `resposta`
   (Text, nullable — a resposta do aluno; escala guardada como texto "0"–"10").
   Tipos portáveis (regra 4).

### Serviço (`kairos/autoavaliacao/service.py`)
3. `TIPOS = ("escala", "texto")`.
4. `criar_autoavaliacao(aluno_id, titulo, perguntas)` — `titulo` obrigatório;
   `perguntas` = lista de `{texto, tipo}` (ignora as de texto vazio); exige **ao menos
   uma pergunta** (senão ValidationError); valida `tipo ∈ TIPOS`; cria a autoavaliação
   (status pendente) + as perguntas em ordem. Loga.
5. `list_autoavaliacoes(aluno_id)` — do aluno, mais recentes primeiro, com status e
   contagem de perguntas (os dois lados leem). `get_detail(autoavaliacao_id)` — com as
   perguntas (+respostas) em ordem, ou None (dono checado na rota).
6. `responder(autoavaliacao_id, respostas)` — `respostas` = `{pergunta_id: valor}`;
   só se `status == "pendente"` (senão ValidationError "Esta autoavaliação já foi
   respondida."); valida por tipo (escala → 0–10; texto → livre); grava cada
   `pergunta.resposta`; marca `status="respondida"` + `respondida_em=agora`. Loga.
   (Respostas em branco permitidas por pergunta? Exigir ao menos as de escala? v1:
   aceitar em branco, mas exigir que **algo** seja respondido — decidir na execução;
   simples: aceitar todas, marcar respondida.)
7. `contar_pendentes(aluno_id)` — nº de autoavaliações pendentes (pro CTA do home).

### Lado do aluno
8. Nova aba **Autoavaliações** na nav do aluno → `GET /aluno/autoavaliacoes`: lista
   **Pendentes** (com "Responder") e **Respondidas** (com "ver"). `aluno_id` da sessão.
9. `GET /aluno/autoavaliacoes/{id}` — **dono→404**. Se pendente: formulário com as
   perguntas (escala = number 0–10; texto = textarea). Se respondida: as perguntas +
   respostas em read-only.
10. `POST /aluno/autoavaliacoes/{id}` (Form: uma entrada por pergunta) — dono→404;
    `responder(...)` → 303 pra `/aluno/autoavaliacoes`. Erro → re-render.
11. No **home**, um CTA quando `contar_pendentes > 0`: "Você tem autoavaliação(ões)
    pendente(s)" → `/aluno/autoavaliacoes` (com selo). (Eco da regra de ouro.)

### Lado do coach
12. Nova sub-aba **Autoavaliações** na ficha → `GET /alunos/{id}/autoavaliacoes`:
    lista as enviadas (status) + um formulário **"Nova autoavaliação"** (título + N
    linhas de pergunta: texto + tipo). 404 se o aluno não existe.
13. `POST /alunos/{id}/autoavaliacoes` — `criar_autoavaliacao(id, titulo, perguntas)`
    → 303 pra a sub-aba. Erro → re-render.
14. `GET /alunos/{id}/autoavaliacoes/{aid}` — o coach vê as perguntas + respostas
    (quando respondida). Confere que a autoavaliação é daquele aluno (senão 404).

### Geral
15. Isolamento: o aluno só vê/responde as próprias (aluno_id da sessão; detalhe
    dono→404); o coach opera por aluno_id na URL. Escrita loga; textos pt-BR. Suíte
    anterior verde.

## Pré-condições
- Área do aluno (Fases 0–3) + gate por papel. HEAD de migração: 0022.

## Arquivos a criar
- `kairos/autoavaliacao/__init__.py`, `models.py` (Autoavaliacao + AutoavaliacaoPergunta),
  `service.py`, `routes.py` (aluno + coach).
- `migrations/versions/0023_create_autoavaliacoes.py`.
- `kairos/templates/area_aluno/autoavaliacoes.html` (lista do aluno),
  `kairos/templates/area_aluno/autoavaliacao_responder.html` (responder/ver),
  `kairos/templates/autoavaliacao/ficha_autoavaliacoes.html` (coach: lista + nova),
  `kairos/templates/autoavaliacao/ficha_autoavaliacao_detalhe.html` (coach: ver
  respostas).
- `tests/test_autoavaliacao.py`.

## Arquivos a modificar
- `kairos/main.py` — incluir o router.
- `kairos/templates/area_aluno/base.html` — item **Autoavaliações** na nav do aluno.
- `kairos/area_aluno/routes.py` — `GET /aluno` injeta `autoavaliacoes_pendentes`
  (contagem) pro CTA.
- `kairos/templates/area_aluno/inicio.html` — o CTA de pendentes.
- `kairos/templates/alunos/ficha_layout.html` — sub-aba **Autoavaliações** (a ficha
  vai a 9 sub-abas; anotar reorganização futura da nav).
- `kairos/static/css/area_aluno.css` — estilos do questionário (perguntas/escala).

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): 2 modelos + migração 0023.
- **serviço** (`servico-writer`): `autoavaliacao/service.py`.
- **aplicação** (`aplicacao-writer`): `autoavaliacao/routes.py` (aluno + coach),
  CTA no home, include no `main.py`.
- **frontend** (`frontend-writer`): telas do aluno (lista + responder) + coach (lista+
  nova + detalhe) + CTA no home + nav + sub-aba.
- **testes** (`teste-writer`): `tests/test_autoavaliacao.py` + suíte verde.

## Fora de escopo (futuro / outras sub-fatias da Fase 4)
- 4a frente+nível, 4b marcadores Kairos, 4d passagem de nível.
- Templates/banco de questionários reutilizáveis; perguntas de múltipla escolha;
  editar/reenviar uma autoavaliação já respondida; alimentar automaticamente os
  Marcadores Kairos (4b) a partir das respostas.
