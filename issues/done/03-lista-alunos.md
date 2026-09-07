# Lista de alunos

## Descrição
Página "Lista de alunos" com o cartão de aluno (nome, objetivo, status, período do plano). Fecha a verificação do comportamento 1: aluno cadastrado aparece na lista.

## Depende de
02-cadastro-aluno

## Especificação funcional
- `GET /alunos` exibe a lista de todos os alunos, ordenada por nome, cada um num cartão com: nome, objetivo, selo de status (Ativo/Inativo) e período do plano ("02/01/2024 → 15/02/2024").
- Campo vazio no cartão mostra "sem registro" (regra 6) — ex.: aluno sem objetivo ou sem período.
- Lista vazia mostra "Nenhum aluno cadastrado." e o botão "Novo aluno".
- Botão/link "Novo aluno" na lista leva a `/alunos/novo`; a página de novo aluno ganha link de volta para a lista.
- O redirect pós-criação (`POST /alunos`) passa a apontar para `/alunos?criado={nome}`, e a mensagem de sucesso "Aluno {nome} cadastrado." aparece na lista — fecha o comportamento 1 do SPEC: cadastrou, aparece na lista.
- `GET /` redireciona para `/alunos` (a lista é o ponto de entrada do sistema, conforme SPEC).
- Datas exibidas no formato brasileiro DD/MM/AAAA; formatação feita no servidor (thin client).

## Pré-condições
- Issues 01 e 02 concluídas (app, banco, cadastro funcionando; suíte com 14 testes verdes).
- Nenhuma dependência nova; nenhuma migração (schema não muda).

## Arquivos a criar
- `kairos/templates/alunos/lista.html` — página da lista: mensagem de sucesso opcional, botão "Novo aluno", cartões (nome, objetivo, selo de status, período) e estado vazio
- `tests/test_lista_alunos.py` — cobre: lista vazia mostra "Nenhum aluno cadastrado."; aluno cadastrado aparece com nome/objetivo/status; campos vazios mostram "sem registro"; fluxo completo cadastro → redirect → nome na lista com mensagem de sucesso; `GET /` redireciona para `/alunos`; ordenação por nome

## Arquivos a modificar
- `kairos/alunos/service.py` — nova função `list_alunos() -> list[dict]` (ordenada por nome, valores primitivos extraídos dentro da sessão)
- `kairos/alunos/routes.py` — nova rota `GET /alunos` (renderiza lista.html, repassa `criado` como mensagem de sucesso); redirect do `POST /alunos` muda de `/alunos/novo?criado=` para `/alunos?criado=`
- `kairos/main.py` — rota `GET /` com RedirectResponse para `/alunos`
- `kairos/templates/alunos/novo.html` — link "← Voltar para a lista"
- `kairos/templates/base.html` — apenas se precisar de CSS novo para cartões/selo (acréscimo, sem mexer no existente)
- `tests/test_cadastro_aluno.py` — ajustar as asserções do destino do redirect (era `/alunos/novo?criado=`, vira `/alunos?criado=`)

## Camadas envolvidas
serviço, rota/página (template), teste

## Status
concluída
