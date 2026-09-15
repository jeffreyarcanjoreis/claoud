# Validação do período do plano

## Descrição
Comportamento 3 do SPEC: período do plano com término anterior ao início é recusado com mensagem clara. Vale no cadastro e na edição, validado no servidor.

## Depende de
06-edicao-perfil

## Especificação funcional
- create_aluno e update_aluno: se plan_start e plan_end presentes e plan_end < plan_start → ValidationError("Término do plano não pode ser anterior ao início.").
- Datas iguais são válidas. Só uma das datas presente é válido.
- Formulários (novo e edição) exibem a mensagem com 400 e valores preservados.

## Pré-condições
Issue 06 concluída.

## Arquivos a criar
Nenhum.

## Arquivos a modificar
- `kairos/alunos/service.py` — validação compartilhada do período
- `tests/test_cadastro_aluno.py` e `tests/test_edicao_perfil.py` — casos: inválido recusado nos dois fluxos, nada gravado; datas iguais aceitas

## Camadas envolvidas
serviço, teste

## Status
concluída
