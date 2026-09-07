# Ligar o treino à agenda — o botão (fatia 9.3)

## Descrição
Da agenda, ver e abrir o treino atribuído àquele dia. A marcação pode apontar para um treino do aluno; a agenda mostra-o com um link "ver treino".

## Especificação funcional
- `sessoes_agendadas.treino_id` opcional (migração 0009, coluna anulável; ORM declara a FK, o serviço garante a integridade).
- `create_sessao` aceita `treino_id`; se dado, valida que o treino existe e pertence ao mesmo aluno (senão ValidationError "Treino inválido."); vazio → NULL.
- `list_sessoes` e `sessoes_de_hoje` trazem `treino_nome` (outer join Treino).
- Formulário de agendar: select "Treino" com os treinos do aluno (opcional; hint quando não há).
- Agenda do aluno e agenda global de hoje (`/agenda`) mostram "Treino: <nome>" com link para `/alunos/{id}/treino/{treino_id}`.

## Arquivos
- Criados: `migrations/versions/0009_add_treino_to_sessoes.py`; `tests/test_agenda_treino.py` (8).
- Modificados: `kairos/agenda/models.py` (+treino_id), `agenda/service.py` (validação + joins + _to_dict), `agenda/routes.py` (treinos no form + treino_id), `painel/routes.py` (_to_hoje_display +treino), templates `agenda/nova.html` (+select), `agenda/lista.html` (+link), `painel/agenda.html` (+link), `components.css` (.field-hint); teste de colunas da sessão (+treino_id) e 6 testes de head → 0009.

## Validação
324 testes verdes. Browser: sessão do Marcos hoje com Treino A associado; link "ver treino" na ficha e em `/agenda` → abre a planilha. Artefactos de verificação removidos da base de dev.

## Status
concluída
