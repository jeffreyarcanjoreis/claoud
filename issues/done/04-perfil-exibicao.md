# Perfil do aluno — exibição

## Descrição
Comportamentos 4 e 5 do SPEC: ao abrir o perfil de um aluno, todos os campos preenchidos são exibidos; campo vazio mostra "sem registro", nunca valor inventado (regra 6 do architecture.md).

## Depende de
02-cadastro-aluno

## Especificação funcional
- `GET /alunos/{id}` exibe o perfil completo: nome, data de nascimento, objetivo, fase atual, período do plano, restrições, alerta, status, observações, data de cadastro.
- Todo campo vazio mostra "sem registro"; datas em DD/MM/AAAA formatadas no servidor.
- id inexistente → 404 com página simples "Aluno não encontrado.".
- O cartão da lista vira link para o perfil; o perfil tem link "← Voltar para a lista".
- Atenção de rota: `/alunos/novo` deve continuar registrado ANTES de `/alunos/{id}` e o id é tipado int.

## Pré-condições
Issues 01-03 concluídas (22 testes verdes).

## Arquivos a criar
- `kairos/templates/alunos/perfil.html` — página do perfil
- `tests/test_perfil_aluno.py` — perfil completo exibido; "sem registro" nos vazios; 404; links de navegação

## Arquivos a modificar
- `kairos/alunos/service.py` — `get_aluno(aluno_id) -> dict | None`
- `kairos/alunos/routes.py` — rota `GET /alunos/{aluno_id}`, reusando os helpers de formatação
- `kairos/templates/alunos/lista.html` — cartão linka para o perfil

## Camadas envolvidas
serviço, rota/página (template), teste

## Status
concluída
