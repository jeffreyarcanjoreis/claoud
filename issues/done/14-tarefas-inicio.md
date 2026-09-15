# Tarefas / lembretes no Início

## Descrição
Uma lista de tarefas do coach na página Início: lembretes, planejamento de publicações/divulgações, campanhas e próximos contatos — tudo que o coach anota. Manual (nada de dado inventado): cada tarefa é criada, marcada como concluída e removida pelo coach.

## Decisões (com o PO)
- Escopo: **só a lista manual** (avisos automáticos sobre alunos ficam para fatias futuras, quando existirem os dados por trás — período do treino, mensagens, campanhas).
- Cada tarefa tem uma **categoria opcional**: lembrete · publicação · contato · campanha.
- Fora desta fatia (registro honesto — regra 6): "alunos prestes a finalizar treino", "mensagens programadas", "campanhas como entidade", "alunos que precisam de suporte" — dependem de dados/funcionalidades que ainda não existem. O único aviso automático calculável hoje ("alunos ativos sem avaliação recente") fica para uma fatia futura.

## Especificação funcional
- O Início (`GET /`) passa a mostrar, abaixo dos tiles, uma seção **"Tarefas"** com: um formulário de adição rápida (título; categoria opcional; prazo opcional) e a lista das tarefas **abertas** (não concluídas).
- As tarefas abertas aparecem ordenadas por prazo ascendente (as sem prazo por último), desempate por ordem de criação.
- Criar uma tarefa com título válido adiciona-a à lista. Título vazio → recusa com mensagem, sem gravar.
- Categoria, quando dada, deve ser uma de: lembrete · publicacao · contato · campanha; fora disso → recusa. Vazia → NULL (exibida sem categoria).
- Prazo é opcional; quando dado, uma data válida; inválida → recusa. Vazio → NULL.
- Cada tarefa aberta mostra o título, a categoria (quando houver, como selo) e o prazo (quando houver); um prazo já passado é marcado como "atrasada".
- **Concluir** uma tarefa marca-a como concluída e ela sai da lista de abertas. **Remover** apaga a tarefa.
- Estado vazio quando não há tarefas abertas ("Nenhuma tarefa em aberto.").
- As ações (criar/concluir/remover) redirecionam de volta ao Início.
- Os 343 testes anteriores continuam verdes; nada do que existe muda de comportamento.

## Pré-condições
- Página Início (`painel/routes.py` `inicio()` + `inicio.html`) existe. Head de migração em 0010. 343 testes verdes.

## Arquivos a criar
- `migrations/versions/0011_create_tarefas.py` — cria a tabela `tarefas` (id; titulo String(200) NOT NULL; categoria String(20) NULL; prazo Date NULL; concluida Boolean NOT NULL server_default false; created_at DateTime server_default now). Tipos portáveis (rule 4); opcionais nullable (rule 6). head → 0011.
- `kairos/tarefas/__init__.py` — pacote do comportamento.
- `kairos/tarefas/models.py` — modelo `Tarefa` espelhando a migração (Mapped/mapped_column).
- `kairos/tarefas/service.py` — `ValidationError`; `CATEGORIAS_VALIDAS=("lembrete","publicacao","contato","campanha")`; `_normalize`, `_parse_titulo_required`, `_parse_categoria_optional`, `_parse_prazo_optional` (date.fromisoformat); `create_tarefa(*, titulo, categoria, prazo) -> dict`; `list_tarefas_abertas() -> list[dict]` (concluida=False, order_by prazo asc nullslast, id asc); `get_tarefa(id) -> Optional[dict]`; `concluir_tarefa(id) -> bool` (seta concluida=True); `remover_tarefa(id) -> bool`. Validação, log nos writes, português nas mensagens.
- `kairos/tarefas/routes.py` — `APIRouter`: `POST /tarefas` (cria via service; erro de validação → re-renderiza o Início com a seção mostrando o erro e os valores, status 400; sucesso → redirect 303 para `/`); `POST /tarefas/{tarefa_id}/concluir` (concluir; 404 se não existe; redirect `/`); `POST /tarefas/{tarefa_id}/remover` (remover; 404 se não existe; redirect `/`).
- `tests/test_tarefa_model.py` — migração cria `tarefas` no head "0011"; colunas exatas; insere/lê de volta (concluida default False; categoria/prazo NULL quando ausentes).
- `tests/test_tarefas.py` — serviço (título obrigatório; categoria inválida recusada; prazo inválido recusado; concluída sai da lista de abertas; ordenação por prazo) e Início/rotas (o Início mostra a seção "Tarefas" e o form; criar via `POST /tarefas` → 303 e a tarefa aparece no Início; criar sem título → 400; concluir → 303 e some da lista; remover → 303 e some; concluir/remover id inexistente → 404).

## Arquivos a modificar
- `kairos/main.py` — importar e registrar `tarefas_router`.
- `kairos/painel/routes.py` — `inicio()` passa `tarefas=[_to_tarefa_display(t) for t in list_tarefas_abertas()]` (formata prazo dd/mm/aaaa, categoria label, flag `atrasada` = prazo < hoje) para o template; importar `list_tarefas_abertas` de `kairos.tarefas.service`.
- `kairos/templates/painel/inicio.html` — nova seção "Tarefas" abaixo dos `.stats`: form de adição rápida (`POST /tarefas`: título, categoria select opcional, prazo date opcional) + lista das abertas (título, selo de categoria, prazo/atrasada, botões "Concluir" e "remover") + estado vazio.
- `kairos/static/css/components.css` — estilos da seção de tarefas (linha da tarefa, selo de categoria, marcação "atrasada", form de adição), reusando tokens/classes existentes onde der.
- `tests/{test_scaffold,test_sessao_agendada_model,test_foto_modelo,test_avaliacao_model,test_perimetria_model,test_exercicio_model,test_treino_model,test_sessao_realizada_model}.py` — HEAD_REVISION "0010"→"0011"; no scaffold, a simulação de migração pendente passa a recuar para '0010' e `DROP TABLE tarefas` (backup carimbado '0010').

## Camadas envolvidas
banco/migração, serviço, aplicação (rotas + Início), frontend (seção no inicio.html + CSS), teste.

## Fora desta fatia
- Avisos automáticos sobre alunos (avaliações em atraso, treino a terminar, etc.) — fatias futuras, e só os que forem calculáveis com dado real.
- Página dedicada de tarefas / histórico de concluídas / editar tarefa (por agora: concluir + remover; a lista mostra só as abertas).
- Categorização por filtro/aba; recorrência; notificações.

## Status
concluída
