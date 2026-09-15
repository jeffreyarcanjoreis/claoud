# Serviço da agenda

## Descrição
Comportamentos 2, 4, 5, 6, 7, 8, 9 (lado da regra): criar uma sessão agendada com validação (data e hora obrigatórias; tipo válido; duração positiva se dada; vazio vira NULL), listar as sessões de um aluno em ordem cronológica, e cancelar (remover) uma sessão. Toda a regra no serviço.

## Depende de
01-agenda-modelo-migracao

## Especificação funcional
- `create_sessao(aluno_id, *, data, hora, tipo, duracao_min=None, observacao=None) -> dict`: recebe valores crus e valida ANTES de persistir (atomicidade):
  - **data** obrigatória (ISO "YYYY-MM-DD") → `date`; ausente/inválida → `ValidationError` ("Data é obrigatória." / "Data inválida.").
  - **hora** obrigatória ("HH:MM") → `time`; ausente/inválida → `ValidationError` ("Hora é obrigatória." / "Hora inválida.").
  - **tipo** obrigatório e ∈ {"individual","grupo"}; fora disso → `ValidationError` ("Tipo inválido.").
  - **duracao_min**: opcional; vazio → None; se dada, inteiro > 0 → senão `ValidationError` ("Duração inválida." / "Duração deve ser positiva.").
  - **observacao**: opcional; vazio → None (regra 6).
  - grava via `session_scope`, loga (id + aluno_id), devolve `_to_dict`.
- `list_sessoes(aluno_id) -> list[dict]`: as sessões do aluno em ordem cronológica ascendente (data asc, hora asc, id asc). Leitura.
- `get_sessao(sessao_id) -> dict | None`.
- `cancel_sessao(sessao_id) -> bool`: apaga a sessão; True se existia e foi apagada, False se não existe. (Cancelar = remover.)
- `_to_dict`: id, aluno_id, data, hora, duracao_min, tipo, observacao, created_at.
- Existência do aluno é garantida pela rota (404), não pelo serviço.

## Nota de arquitetura (gancho do Google Calendar)
O `create_sessao`/`cancel_sessao` são os pontos naturais onde a sincronização futura com o Google Calendar vai enganchar (um `agenda/sync.py` isolado). Nesta fatia NÃO se implementa nada de Google — só se mantém a fronteira limpa (o serviço não sabe do Google; a base é a fonte de verdade).

## Pré-condições
- Issue 01 concluída: modelo `SessaoAgendada` e tabela existem. Padrão do serviço de avaliações como referência. 234 testes verdes.

## Arquivos a criar
- `kairos/agenda/service.py` — no estilo de `kairos/avaliacoes/service.py`: `ValidationError` própria; `TIPOS_VALIDOS = ("individual", "grupo")`; helpers `_normalize`, `_parse_date_required`, `_parse_time_required` (`datetime.time.fromisoformat`), `_parse_duracao`; `_to_dict`; `create_sessao`, `list_sessoes`, `get_sessao`, `cancel_sessao`. Importa `SessaoAgendada` de `kairos.agenda.models`.
- `tests/test_agenda_servico.py` — criar válido grava e volta (data/hora/tipo/duração corretos); sem data → ValidationError e nada gravado; sem hora → ValidationError; tipo inválido ("x") → ValidationError; duração 0 ou negativa → ValidationError; duração vazia → None; observação vazia → None; `list_sessoes` em ordem cronológica (cria 3 fora de ordem, confere); `get_sessao` id inexistente → None; `cancel_sessao` remove (list fica sem ela) e devolve True; `cancel_sessao` de id inexistente → False.

## Arquivos a modificar
- Nenhum (módulo novo autocontido; as rotas consomem nas issues 03-06).

## Camadas envolvidas
serviço, teste

## Status
concluída
