# Execução do aluno — na página do treino

## Descrição
Na página do treino do aluno, o aluno marca cada exercício como feito (com progresso da sessão), registra carga/reps reais e escreve uma observação da execução (o verbo é dele; regras 11–14). Comportamentos [F+] 18 (marcar feito + progresso), 19, 20 (UI).

## Depende de
09 (dados + serviço da execução)

## Status
concluída

## Especificação funcional
Só UI + rota do aluno; toda regra já está no serviço da fatia 09 (`registrar_execucao`, `execucoes_do_treino`, `progresso_sessao`). Tudo é do **dia de hoje** (a data default do serviço). Fidelidade ao método (regras 11–14): é o aluno registrando o que realmente fez, em primeira pessoa; nada de nota/cobrança — é o espelho do que aconteceu hoje.

- **Rota (aluno, `kairos/area_aluno/routes.py`):**
  - `POST /aluno/treinos/{treino_id}/itens/{item_id}/execucao` (form: `feito` checkbox opcional, `carga_real`, `reps_real`, `observacao`): gate do aluno (`_aluno_id_da_sessao`; `get_treino`→404 se não é do aluno; `get_item`→404 se o item não é do treino). `feito_bool = feito is not None` (checkbox: presente=marcado). `registrar_execucao(item_id, feito=feito_bool, carga_real=..., reps_real=..., observacao=...)`; em `ValidationError` no-op; 303 de volta para `/aluno/treinos/{treino_id}`.
  - **Ajuste no GET `treino_detalhe`:** usar `execucoes_do_treino(treino_id)` (default hoje) e, para cada item de `detalhe["itens"]`, setar `item["execucao"] = mapa.get(item["id"])` **antes** de `agrupar_itens_por_fase`. Passar também `progresso = progresso_sessao(treino_id)` no contexto. Não quebrar os campos já passados (treino.id/nome/apresentacao, fases, variações, "meu lugar hoje", vídeo).
- **Template (`kairos/templates/area_aluno/treino_detalhe.html`):**
  - **Progresso da sessão** no topo: "Feitos: {{ progresso.feitos }} de {{ progresso.total }}" com barra simples (largura = feitos/total, protegida por `{% if progresso.total %}`; total 0 → "0 de 0", sem barra). Copy acolhedora ("meu progresso de hoje"), não cobrança.
  - **Por exercício**, form `POST /aluno/treinos/{{ treino.id }}/itens/{{ i.id }}/execucao` com: checkbox **Feito** (marcado se `i.execucao and i.execucao.feito`); **carga real** (`carga_real`, prefill); **reps reais** (`reps_real`, prefill); **observação** (`observacao` textarea, prefill, rótulo em primeira pessoa "como foi para mim hoje"); botão "Registrar". Selo "registrado hoje" quando `i.execucao`. Sem execução → campos vazios (regra 6), sem placeholder falso.
  - Manter read-only já existente (planilha, variações, "meu lugar hoje", vídeo).
- **CSS:** barra de progresso discreta (acento do tema no preenchimento) e layout do bloco de execução no card.

Casos de borda: treino/item de outro aluno → 404; marcar feito sem carga/reps → grava feito com NULL; registrar de novo hoje → upsert (serviço); total 0 → "0 de 0" sem barra; observação vazia → NULL.

## Pré-condições
- Fatia 09 concluída (serviço da execução, commitada). Head 0029 (sem schema novo nesta fatia).
- GET `/aluno/treinos/{treino_id}` já existe e agrupa por fase.

## Arquivos a modificar
- `kairos/area_aluno/routes.py` — rota POST execução + enriquecer o GET.
- `kairos/templates/area_aluno/treino_detalhe.html` — barra de progresso + bloco de execução por exercício.
- `kairos/static/css/components.css` — barra de progresso + bloco de execução.

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): rota POST + enriquecimento do GET.
- **frontend** (`frontend-writer`): progresso + form de execução por exercício + CSS.
- **testes** (`teste-writer`): `tests/test_treino_execucao_aluno.py` — POST grava (feito/carga/reps/observação) e o GET reflete (prefill + selo); progresso sobe conforme marca feito; treino/item de outro aluno → 404; checkbox ausente → feito False; registrar de novo atualiza (upsert, não duplica); total 0 → "0 de 0" sem barra. Auth de aluno logado. Sem migração (head 0029). Suíte completa verde.
