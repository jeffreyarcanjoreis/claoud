# Feedback do coach sobre a execução

## Descrição
O coach vê o anexo enviado pelo aluno e deixa um feedback naquele exercício; o aluno lê o feedback no card do exercício. Comportamentos [F+] 22 e 23.

## Depende de
11 (o anexo que o coach analisa)

## Status
concluída

## Especificação funcional
O feedback é **por anexo** (`AnexoExecucao`): o coach responde ao que o aluno enviou (vídeo/foto + observação daquele anexo). Um feedback corrente por anexo, revisável (sobrescreve; sem histórico). Fidelidade ao método (regras 11–14): o coach **acolhe/educa/espelha** — orienta, não gradua nem pune. Regra 6: feedback vazio = NULL = "sem feedback ainda".

- **Dados (migração 0031):** adicionar a `anexos_execucao` a coluna `feedback_coach` (`Text`, nullable). Model `AnexoExecucao` ganha `feedback_coach: Mapped[Optional[str]] = mapped_column(Text, nullable=True)`. Head 0030 → **0031**.
- **Serviço (`kairos/execucao/service.py`):**
  - `set_feedback_anexo(anexo_id, feedback=None) -> Optional[Dict]`: normaliza `feedback` (vazio→None); get-or-None; persiste `feedback_coach`; loga; retorna o dict do anexo (com `feedback_coach`).
  - `_anexo_to_dict`, `get_anexo`, `list_anexos`, `anexos_do_treino` passam a incluir `feedback_coach`.
- **Rota (coach, `kairos/treinos/routes.py`):**
  - `POST /alunos/{aluno_id}/anexos/{anexo_id}/feedback` (form `feedback`): gate de coach (mesmo da rota que serve o anexo do coach: `get_aluno`; anexo→item→treino; `treino["aluno_id"] == aluno_id`), senão 404. `set_feedback_anexo(anexo_id, feedback)`; 303 de volta à planilha do coach (`/alunos/{aluno_id}/treino/{treino_id}` — descubra `treino_id` via item).
- **Templates:**
  - `treinos/aluno_detalhe.html` (coach): em cada anexo listado (fatia 11), abaixo da mídia/observação, um form `POST /alunos/{{ aluno.id }}/anexos/{{ anexo.id }}/feedback` com `<textarea name="feedback">` pré-preenchido com `anexo.feedback_coach` e botão "Salvar feedback". Copy no tom do coach (orientar/acolher).
  - `area_aluno/treino_detalhe.html` (aluno): em cada anexo, quando `anexo.feedback_coach` existir, uma linha/box read-only tipo "Feedback do coach: {{ anexo.feedback_coach }}" (o aluno lê; não edita). Sem feedback → nada (regra 6).
- **CSS:** caixa de feedback discreta (acento do tema; diferenciar visualmente a voz do coach da observação do aluno).

Casos de borda: anexo de outro aluno → 404; feedback vazio → limpa (NULL); anexo inexistente → 404; feedback só aparece ao aluno quando preenchido.

## Pré-condições
- Fatia 11 concluída (anexos existem, com `_anexo_to_dict`/`anexos_do_treino` e as rotas de servir). Head 0030. Esta fatia adiciona **0031**.

## Arquivos a modificar
- `migrations/versions/0031_add_feedback_to_anexos.py` — nova migração.
- `kairos/execucao/models.py` — coluna `feedback_coach` em `AnexoExecucao`.
- `kairos/execucao/service.py` — `set_feedback_anexo` + `feedback_coach` nos dicts (`_anexo_to_dict` cobre get/list/anexos_do_treino).
- `kairos/treinos/routes.py` — rota POST feedback (coach).
- `kairos/templates/treinos/aluno_detalhe.html` — form de feedback por anexo (coach).
- `kairos/templates/area_aluno/treino_detalhe.html` — leitura do feedback por anexo (aluno).
- `kairos/static/css/components.css` — caixa de feedback.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): migração 0031 + coluna no model.
- **serviço** (`servico-writer`): `set_feedback_anexo` + `feedback_coach` em `_anexo_to_dict`.
- **aplicação** (`aplicacao-writer`): rota POST feedback (coach, gate + 404 + 303).
- **frontend** (`frontend-writer`): form de feedback (coach) + leitura (aluno) + CSS.
- **testes** (`teste-writer`): `tests/test_treino_feedback.py` — `set_feedback_anexo` grava/limpa; `get_anexo`/`anexos_do_treino` expõem `feedback_coach`; rota do coach grava e a planilha reflete; anexo de outro aluno → 404; o aluno vê o feedback no card quando preenchido, nada quando vazio. Atualizar `HEAD_REVISION` 0030→0031 + `test_scaffold` + `test_anexo_model` (coluna nova). Suíte completa verde.
