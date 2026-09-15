# Idade derivada da data de nascimento

## Descrição
Comportamento 8 do SPEC: quando a data de nascimento está preenchida, o perfil exibe a idade calculada a partir dela. Cálculo no servidor (thin client).

## Depende de
04-perfil-exibicao

## Especificação funcional
- Perfil mostra "Idade: N anos" calculada da data de nascimento (aniversário ainda não feito no ano conta a menos).
- Sem data de nascimento → "Idade: sem registro".
- Cálculo é regra de negócio: vive no serviço (`get_aluno` retorna `age`), não no template.

## Pré-condições
Issue 04 concluída.

## Arquivos a criar
Nenhum (testes entram em tests/test_perfil_aluno.py).

## Arquivos a modificar
- `kairos/alunos/service.py` — cálculo de `age` em get_aluno
- `kairos/alunos/routes.py` / `kairos/templates/alunos/perfil.html` — exibição
- `tests/test_perfil_aluno.py` — idade correta (incluindo aniversário não feito); sem nascimento → "sem registro"

## Camadas envolvidas
serviço, rota/página (template), teste

## Status
concluída
