# Status ativo/inativo

## Descrição
Comportamento 7 do SPEC: o coach marca um aluno como inativo e ele permanece na lista, identificado pelo selo de status.

## Depende de
06-edicao-perfil

## Especificação funcional
- Marcar inativo acontece pelo formulário de edição (select de status já existente).
- Aluno inativo permanece na lista com selo "Inativo" (cinza); perfil também mostra o status.
- Nenhum código novo esperado além do que a issue 06 entrega — esta issue é fechada por testes que provam o comportamento de ponta a ponta.

## Pré-condições
Issue 06 concluída.

## Arquivos a criar
Nenhum.

## Arquivos a modificar
- `tests/test_edicao_perfil.py` — editar para inativo → lista continua mostrando o aluno com "Inativo"; voltar para ativo funciona

## Camadas envolvidas
teste

## Status
concluída
