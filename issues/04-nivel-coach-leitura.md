# Coach lê o nível do aluno (ficha, só leitura)

## Descrição
Na ficha do aluno, o coach vê o nível atual que o aluno reconheceu, o histórico e as notas — só leitura, "sem registro" quando o aluno ainda não se reconheceu. Em nenhum lugar o coach define o nível (o coach acompanha; a conscientização ativa fica fora desta fatia).

## Depende de
01 (frente na ficha — onde a seção se acomoda), 02 (dados + serviço do nível)

## Status
planejada

## Especificação funcional
Espelha EXATAMENTE o padrão da sub-aba de coach do domínio `checkin`: uma rota `GET /alunos/{aluno_id}/...` em `kairos/checkin/routes.py` (`coach_checkins`) renderiza `checkin/ficha_checkins.html` (que estende `alunos/ficha_layout.html`) com `aluno=ficha_header(aluno)` e `subtab`, e há um link na subnav de `ficha_layout.html`. Mantém a lógica do nível dentro do módulo `nivel` (isolamento), sem acoplar `alunos/routes.py`.

- **Nova sub-aba "Nível" na ficha do coach** → `GET /alunos/{aluno_id}/nivel` (no `kairos/nivel/routes.py`, lado do coach; `aluno_id` da URL, pois o coach gere todos):
  - `get_aluno(aluno_id)`; se `None` → página 404 (`alunos/nao_encontrado.html`, `status_code=404`), mesmo padrão do `coach_checkins`.
  - `atual = nivel_atual(aluno_id)` (dict ou None) → exibe `atual["nivel_label"]` + `atual["nota"]` (se houver) + data, ou "sem registro" quando None ("aguardando o aluno se reconhecer").
  - `historico = list_reconhecimentos(aluno_id)` → lista (data, nível label, nota), mais recente primeiro; read-only.
  - Renderiza `nivel/ficha_nivel.html` com `aluno=ficha_header(aluno)`, `subtab="nivel"`, `nivel_atual` (display) e `historico` (lista de display).
- **Só leitura:** nenhum formulário, nenhum POST, o coach NUNCA define/edita o nível (regras 11–14: o coach acompanha, não classifica). Quando não há reconhecimento: "sem registro".
- Isolamento: a leitura é por `aluno_id` da URL (padrão do coach, igual às outras sub-abas da ficha).

Casos de borda: aluno inexistente → 404; aluno sem reconhecimento → "sem registro" / histórico vazio; notas vazias não aparecem (regra 6).

## Pré-condições
- Issue 02 concluída (`kairos.nivel.service`: `nivel_atual`, `list_reconhecimentos`, `NIVEL_LABELS`). `ficha_header` existe em `kairos.web`. A ficha do coach (`alunos/ficha_layout.html` com subnav) existe. HEAD de migração: 0024.

## Arquivos a criar
- `kairos/templates/nivel/ficha_nivel.html` — estende `alunos/ficha_layout.html`; bloco `ficha_content`: seção "Nível reconhecido" (o atual: label + data + nota, ou "sem registro"/"aguardando o aluno se reconhecer") e "Histórico" (lista read-only de data · nível · nota); vazio → mensagem. Reusa classes da ficha (`card-list`/`card`/`card-title`/`card-line`/`none`/`coming-soon`), como `checkin/ficha_checkins.html` e `acompanhamento/lista.html`.

## Arquivos a modificar
- `kairos/nivel/routes.py` — adicionar a rota de coach `GET /alunos/{aluno_id}/nivel` (`coach_nivel`), importando `get_aluno` (já importado), `ficha_header` (`kairos.web`), e reusando `nivel_atual`/`list_reconhecimentos`/`NIVEL_LABELS` já importados. Helper de display do histórico/atual (data `%d/%m/%Y`, `nivel_label`, `nota`).
- `kairos/templates/alunos/ficha_layout.html` — adicionar o link **"Nível"** na `nav.subnav` (ex.: logo após "Treino" ou junto de "Acompanhamento"): `<a class="{% if subtab == 'nivel' %}on{% endif %}" href="/alunos/{{ aluno.id }}/nivel">Nível</a>`.

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): rota de coach `GET /alunos/{aluno_id}/nivel` em `kairos/nivel/routes.py`.
- **frontend** (`frontend-writer`): template `nivel/ficha_nivel.html` + link "Nível" na subnav de `ficha_layout.html`.
- **testes** (`teste-writer`): `tests/test_nivel_coach.py` — coach auto-logado: `GET /alunos/{id}/nivel` 200 mostrando o nível atual e o histórico quando há reconhecimentos (crie via `kairos.nivel.service.reconhecer`), "sem registro" quando não há; 404 para aluno inexistente; confirmar que NÃO existe POST/edição de nível pelo coach (a rota é só GET). Suíte anterior verde.
