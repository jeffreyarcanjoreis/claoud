# Arco da sessão — aluno (read-only)

## Descrição
Na página do treino do aluno, o arco das 5 fases com os minutos proporcionais aparece read-only no topo. Comportamento [F1] 4.

## Depende de
13 (serviço `arco_da_sessao`), 14 (o componente de arco já existe)

## Status
concluída

## Especificação funcional
Só UI do aluno; reusa o componente de arco criado na 14 (mesma marcação/CSS). Read-only — o aluno não define duração.

- **Rota (aluno, `kairos/area_aluno/routes.py`):** no GET `treino_detalhe` (`/aluno/treinos/{treino_id}`), adicionar ao contexto `arco = arco_da_sessao(treino_id)` (ou None). Manter todos os campos já passados (treino, fases, progresso, execução, anexos).
- **Template (`kairos/templates/area_aluno/treino_detalhe.html`):** no topo (após o cabeçalho/apresentação, antes/junto do progresso), quando houver `arco`, renderizar o **mesmo componente de arco** da planilha do coach (5 fases proporcionais ao tempo, com fase, pergunta e minutos), em modo leitura. Sem arco → nada (regra 6). Reutilizar as classes CSS da 14 (ex. `.arco`/`.arco-fase`); se fizer sentido, extrair o componente para um partial Jinja incluído nos dois templates.
- **CSS:** reutilizar o da 14; nenhum estilo novo, salvo ajuste mínimo se o contexto do aluno pedir.

Casos de borda: treino sem duração → sem arco; o aluno não vê seletor de duração nem forms (só leitura).

## Pré-condições
- Fatias 13 e 14 concluídas. Head 0032 (sem schema novo).

## Arquivos a modificar
- `kairos/area_aluno/routes.py` — `arco` no contexto do GET do treino do aluno.
- `kairos/templates/area_aluno/treino_detalhe.html` — componente de arco read-only.
- (opcional) `kairos/templates/treinos/_arco.html` — partial compartilhado, se extrair o componente.

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): `arco` no contexto do GET do aluno.
- **frontend** (`frontend-writer`): arco read-only (reusando a 14) + eventual extração de partial.
- **testes** (`teste-writer`): `tests/test_treino_arco_aluno.py` — aluno logado dono: o GET do treino mostra o arco com os minutos certos quando há duração; sem duração → sem arco; sem seletor/forms de duração na página do aluno. Suíte completa verde.
