# Edição do perfil

## Descrição
Comportamento 6 do SPEC: o coach edita um campo do perfil e salva; o novo valor aparece imediatamente no perfil e na lista. Reusa o formulário de perfil do cadastro.

## Depende de
04-perfil-exibicao

## Especificação funcional
- `GET /alunos/{id}/editar` mostra o formulário pré-preenchido com os valores atuais (datas em ISO nos inputs).
- `POST /alunos/{id}` grava via mesma normalização/validação do cadastro e redireciona 303 para o perfil com mensagem "Perfil atualizado.".
- Erro de validação → 400 re-renderizando o formulário com a mensagem e os valores digitados.
- id inexistente → 404. Toda atualização gera log.
- O formulário vira parcial compartilhado (`_form.html`) usado por novo.html e editar.html.

## Pré-condições
Issue 04 concluída.

## Arquivos a criar
- `kairos/templates/alunos/_form.html` — parcial do formulário (campos + erro)
- `kairos/templates/alunos/editar.html` — página de edição
- `tests/test_edicao_perfil.py` — pré-preenchimento; salvar muda perfil e lista; erro preserva valores; 404

## Arquivos a modificar
- `kairos/alunos/service.py` — `update_aluno(aluno_id, **raw) -> dict | None` (mesma normalização do create)
- `kairos/alunos/routes.py` — rotas GET editar / POST update
- `kairos/templates/alunos/novo.html` — passa a usar o parcial
- `kairos/templates/alunos/perfil.html` — botão "Editar" e mensagem de sucesso

## Camadas envolvidas
serviço, rota/página (template), teste

## Status
concluída
