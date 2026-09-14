# Estrutura do treino — planilha do aluno (ver em fases)

## Descrição
Na página do treino do aluno (`/aluno/treinos/{treino_id}`, só leitura): os exercícios passam a aparecer agrupados nas 5 fases (ordem canônica, cada fase com sua pergunta-guia, grupo "Sem fase" ao fim), com a apresentação do treino no topo e a observação do coach em cada exercício quando houver. Comportamentos [F1] 5, 8, 10 (aluno).

## Depende de
01 (serviço + agrupamento), 02 (mesmos blocos de fase já consolidados no coach)

## Status
concluída

## Especificação funcional
Reaproveita a rota `treino_detalhe` (`GET /aluno/treinos/{treino_id}`) e o template `area_aluno/treino_detalhe.html`, ambos já existentes e só-leitura. O serviço (issue 01) já entrega `agrupar_itens_por_fase` e os itens com `fase`/`fase_label`/`observacao`; a apresentação é `detalhe["observacao"]`.

- **Agrupamento:** a rota passa a montar `fases = agrupar_itens_por_fase(detalhe["itens"])` e a enviar ao template, além do treino (nome + apresentação). O template mostra um **bloco por fase** na ordem canônica: cabeçalho com `fase_label` + `fase_pergunta`; os exercícios daquela fase (mesma tabela `planilha` de hoje, com a observação do coach quando houver via `item-obs`); "nenhum exercício nesta fase" quando vazio; o grupo "Sem fase" só aparece quando há itens sem fase (o serviço já cuida).
- **Apresentação:** no topo, mostra a apresentação do treino (`detalhe["observacao"]`) quando existe; senão nada (é leitura — sem "sem registro" chamativo para o aluno; simplesmente não mostra o bloco).
- **Isolamento:** mantém o padrão atual (aluno_id da sessão; treino de outro aluno ou inexistente → `_nao_encontrado` 404, nunca 403). Só leitura: nenhum formulário/botão de edição.

Casos de borda: treino sem exercícios → 5 blocos vazios com "nenhum exercício nesta fase"; itens sem fase → bloco "Sem fase" ao fim; sem apresentação → sem o bloco do topo.

## Pré-condições
- Issue 01 concluída (`agrupar_itens_por_fase`, itens com fase). A rota `treino_detalhe` e `area_aluno/treino_detalhe.html` existem. Auth: aluno (área do aluno).

## Arquivos a modificar
- `kairos/area_aluno/routes.py` — na `treino_detalhe`: importar `agrupar_itens_por_fase` de `kairos.treinos.service` (já importa `get_treino`/`get_treino_detail`/`list_treinos` de lá); montar `fases = agrupar_itens_por_fase(detalhe["itens"])`; passar contexto `{"treino": {"nome": detalhe["nome"], "apresentacao": detalhe["observacao"] or None}, "fases": fases}`.
- `kairos/templates/area_aluno/treino_detalhe.html` — apresentação no topo (quando houver); render agrupado por fase (bloco com `fase_label` + `fase_pergunta`; tabela `planilha` com observação do coach; "nenhum exercício nesta fase"); manter o link "voltar". Reusar classes existentes (`cad-card`, `planilha`, `table-wrap`, `item-obs`, `aluno-vazio`, e as `.fase-bloco`/`.fase-titulo`/`.fase-pergunta` já criadas na issue 02).

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): agrupar por fase na `treino_detalhe` de `kairos/area_aluno/routes.py`.
- **frontend** (`frontend-writer`): `area_aluno/treino_detalhe.html` (apresentação + blocos de fase, leitura).
- **testes** (`teste-writer`): `tests/test_treino_aluno_fases.py` — logado como aluno, `GET /aluno/treinos/{id}` mostra os labels das fases + pergunta-guia; um exercício com fase aparece sob a fase; apresentação aparece quando definida; observação do coach aparece; isolamento (treino de outro aluno → 404). `_login_as_aluno` patchando `current_user` em `kairos.auth.middleware` e `kairos.area_aluno.routes`. Suíte anterior verde.
