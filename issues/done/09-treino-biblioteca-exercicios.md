# Biblioteca de exercícios (fatia 9.1 — início da capacidade Treino)

## Descrição
A fundação do Treino: um acervo de exercícios (nome, grupo muscular, observação) numa área própria "Treinos". Primeira das três sub-fatias (9.1 biblioteca → 9.2 montar treinos → 9.3 ligar à agenda).

## Decisões (com o PO)
Ancoradas na planilha real do Marcos (divisão semanal dia→foco+cardio):
- O botão da agenda abrirá **o treino atribuído** à marcação (não um log de execução).
- Ligação treino↔dia **manual por marcação**.
- O vínculo vive nas **sessões Kairos** (Google Calendar é só-leitura, sem ID estável).

## Especificação funcional
- Separador "Treinos" na navegação → `/treinos` (biblioteca, ordenada por nome case-insensitive) + `/treinos/novo` (formulário).
- Criar exercício com nome válido grava e mostra na lista; sem nome → recusa com mensagem, sem gravar, valores preservados.
- Grupo/observação vazios → NULL, exibidos como "sem registro" (rule 6).
- Estado vazio quando não há exercícios.
- 286 testes anteriores continuam verdes.

## Arquivos criados
- `migrations/versions/0007_create_exercicios.py` (head 0007).
- `kairos/treinos/__init__.py`, `models.py` (`Exercicio`), `service.py` (create/list/get/count + ValidationError), `routes.py` (`/treinos`, `/treinos/novo`, POST `/treinos`).
- `kairos/templates/treinos/exercicios_lista.html`, `exercicio_form.html`.
- `tests/test_exercicio_model.py` (3), `tests/test_treinos_biblioteca.py` (9).

## Arquivos modificados
- `kairos/main.py` — regista `treinos_router`.
- `kairos/templates/base.html` — separador "Treinos".
- `tests/{test_scaffold,test_sessao_agendada_model,test_foto_modelo,test_avaliacao_model,test_perimetria_model}.py` — head 0006→0007 (scaffold: simulação 0005→0006, DROP exercicios).

## Camadas envolvidas
banco/migração, serviço, aplicação (rotas), frontend (templates), teste

## Validação
298 testes verdes. Browser: separador Treinos + estado vazio; exercício criado e listado de ponta a ponta ("Supino reto com barra", Peito). Dado de teste removido da base de dev (sem UI de apagar ainda).

## Status
concluída
