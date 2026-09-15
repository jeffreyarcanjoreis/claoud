# Montar treinos / planilha na ficha do aluno (fatia 9.2)

## Descrição
Sub-aba "Treino" (nova) na ficha do aluno: montar treinos nomeados compostos de exercícios da biblioteca, cada um com séries/reps/carga opcionais (a "planilha").

## Especificação funcional
- Modelos `Treino` (aluno_id, nome, observacao) e `TreinoItem` (treino_id, exercicio_id, ordem, series, reps, carga, observacao); migração 0008.
- Serviço: create_treino (nome obrigatório), list_treinos (com item_count), get_treino_detail (itens juntados ao nome/grupo do exercício, ordenados), add_item_to_treino (exercício válido obrigatório, séries positivo se dado, ordem incremental), remove_item, delete_treino (cascata), get_treino/get_item (ownership).
- Rotas: sub-aba `/alunos/{id}/treino`, `/novo`, POST cria e redireciona à planilha; `/{treino_id}` mostra planilha + form de adicionar; POST itens (adicionar), POST item remover, POST apagar treino. Verificação de dono em todas (404 cruzado).
- Vazios → NULL, exibidos como "sem registro".

## Arquivos
- Criados: `migrations/versions/0008_create_treinos.py`; templates `treinos/aluno_lista.html`, `aluno_novo.html`, `aluno_detalhe.html`; `tests/test_treino_model.py` (3), `tests/test_treinos_planilha.py` (15).
- Modificados: `kairos/treinos/models.py` (+Treino, +TreinoItem), `service.py` (+funções de treino), `routes.py` (+rotas da sub-aba); `kairos/templates/alunos/ficha_layout.html` (+sub-aba Treino); `kairos/static/css/components.css` (+planilha/botões); 6 testes de head → 0008.

## Validação
316 testes verdes. Browser: Treino A do Marcos (Supino/Tríceps/Agachamento com séries·reps·carga) renderizado na planilha; artefactos removidos da base de dev.

## Status
concluída
