# Filtro da lista por status

## Descrição
Comportamento 9 do SPEC: ao filtrar a lista por status, apenas os alunos daquele status aparecem.

## Depende de
08-status-inativo

## Especificação funcional
- `GET /alunos?status=active` mostra só ativos; `?status=inactive` só inativos; sem parâmetro, todos.
- Links de filtro na página: "Todos | Ativos | Inativos", com o filtro atual destacado.
- Valor de status desconhecido no query param é ignorado (mostra todos) — defensivo, sem 500.
- Filtragem no servidor (query SQL), não no template.

## Pré-condições
Issue 08 concluída.

## Arquivos a criar
- `tests/test_filtro_status.py` — só ativos; só inativos; sem filtro todos; valor desconhecido mostra todos; links presentes

## Arquivos a modificar
- `kairos/alunos/service.py` — `list_alunos(status=None)` com filtro na query
- `kairos/alunos/routes.py` — query param repassado + estado do filtro para o template
- `kairos/templates/alunos/lista.html` — links de filtro

## Camadas envolvidas
serviço, rota/página (template), teste

## Status
concluída
