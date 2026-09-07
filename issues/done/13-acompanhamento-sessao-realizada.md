# Acompanhamento — registrar a sessão realizada

## Descrição
Fechar o ciclo do coach: além de agendar (sessão agendada), registrar o que aconteceu (a *sessão realizada*) — presença, disposição com que o aluno chegou, e um feedback livre de como foi. Vive na ficha do aluno, na sub-aba que hoje é "Feedback (em breve)", renomeada para **"Acompanhamento"**.

## Decisões (com o PO)
- Modelo do registro: **enxuto + disposição** — data + presença + disposição do aluno + feedback livre. (Sem RPE nem vínculo ao treino nesta fatia.)
- Sub-aba renomeada de "Feedback" para **"Acompanhamento"** (mais fiel ao domínio).
- Fatia autônoma: listar + registrar. O botão "marcar como realizada" na agenda fica para fatia futura.

## Distinção de domínio
`SessaoAgendada` (fatia 7, o que está marcado) ≠ `SessaoRealizada` (esta fatia, o que aconteceu). São entidades diferentes; esta não referencia aquela nesta fatia.

## Especificação funcional
- A sub-aba "Acompanhamento" da ficha lista as sessões realizadas do aluno, da mais recente para a mais antiga (data desc), cada uma com data, presença, disposição (ou "sem registro") e o feedback quando houver; botão "Registrar sessão"; estado vazio quando não há.
- Registrar com data e presença válidas cria o registro, que passa a aparecer na lista.
- Presença é obrigatória e uma de: **compareceu · faltou · remarcada**. Fora disso → recusa com mensagem, sem gravar.
- Data é obrigatória; ausente/ inválida → recusa com mensagem.
- Disposição é opcional; quando dada, uma de: **ótima · boa · neutra · baixa · muito baixa**; fora disso → recusa. Vazia → NULL, exibida como "sem registro" (rule 6).
- Feedback é opcional; vazio → NULL.
- Remover um registro tira-o da lista; remover registro de outro aluno pela URL errada → 404 (verificação de dono).
- id de aluno inexistente nas rotas → 404.
- Os 330 testes anteriores continuam verdes; nada do que existe muda de comportamento (a rota antiga `/alunos/{id}/feedback` permanece, apenas deixa de ser linkada — órfã inofensiva, cleanup futuro).

## Pré-condições
- Ficha do aluno com `ficha_layout.html` e o helper `_render_ficha`/`ficha_header` (existem). Head de migração em 0009. 330 testes verdes.

## Arquivos a criar
- `migrations/versions/0010_create_sessoes_realizadas.py` — cria a tabela `sessoes_realizadas` (id, aluno_id FK NOT NULL + índice, data Date NOT NULL, presenca String(20) NOT NULL, disposicao String(20) NULL, feedback Text NULL, created_at DateTime server_default now). Só tipos portáveis (rule 4); opcionais nullable (rule 6). head → 0010.
- `kairos/acompanhamento/__init__.py` — pacote do comportamento.
- `kairos/acompanhamento/models.py` — `SessaoRealizada` espelhando a migração (Mapped/mapped_column).
- `kairos/acompanhamento/service.py` — `ValidationError`; `PRESENCA_VALIDAS=("compareceu","faltou","remarcada")`, `DISPOSICOES_VALIDAS=("ótima","boa","neutra","baixa","muito baixa")`; `create_sessao_realizada(aluno_id, *, data, presenca, disposicao, feedback)`, `list_sessoes_realizadas(aluno_id)` (data desc, id desc), `get_sessao_realizada(id)`, `remover_sessao_realizada(id)->bool`. Validação e normalização (vazio→NULL). Português nas mensagens; código em inglês.
- `kairos/acompanhamento/routes.py` — `APIRouter`: `GET /alunos/{id}/acompanhamento` (lista, sub-aba, `ficha_header`+subtab "acompanhamento"), `GET /alunos/{id}/acompanhamento/novo` (form; "novo" declarado antes de qualquer paramétrica), `POST /alunos/{id}/acompanhamento` (cria, valida via service, re-renderiza o form com erro+valores preservados no 400, redireciona no sucesso), `POST /alunos/{id}/acompanhamento/{registro_id}/remover` (verifica dono → 404). Rotas finas, sem regra de negócio.
- `kairos/templates/acompanhamento/lista.html` — estende `alunos/ficha_layout.html` (block ficha_content): título + botão "Registrar sessão"; lista (`.card-list`/`.card`) com data · presença · disposição · feedback e um botão "Remover" (POST); estado vazio.
- `kairos/templates/acompanhamento/novo.html` — estende o ficha_layout: form (data; presença select obrigatório; disposição select opcional com "— sem registro —"; feedback textarea), com o guard anti-"None" `(values.x if values else '') or ''`, botão "Salvar", link voltar.
- `tests/test_sessao_realizada_model.py` — migração cria `sessoes_realizadas` no head "0010"; colunas exatas (sem derivados); insere/lê de volta com opcionais NULL.
- `tests/test_acompanhamento.py` — serviço (data+presença obrigatórias; presença/disposição inválidas recusadas; disposição vazia→None; lista em ordem data desc) e rotas (sub-aba vazia; 404 aluno inexistente; criar+redirect; sem presença→400 com valores preservados; remover; remover de outro aluno→404; sub-aba "Acompanhamento" presente e sem "em breve").

## Arquivos a modificar
- `kairos/main.py` — importar e registrar `acompanhamento_router`.
- `kairos/templates/alunos/ficha_layout.html` — trocar o item de subnav "Feedback<span class="soon">em breve</span>" (href `/alunos/{id}/feedback`, subtab 'feedback') por "Acompanhamento" (href `/alunos/{id}/acompanhamento`, subtab 'acompanhamento', sem "em breve").
- `tests/{test_scaffold,test_sessao_agendada_model,test_foto_modelo,test_avaliacao_model,test_perimetria_model,test_exercicio_model,test_treino_model}.py` — HEAD_REVISION "0009"→"0010"; no scaffold, a simulação de migração pendente passa a recuar para '0009' e `DROP TABLE sessoes_realizadas` (backup carimbado '0009').

## Camadas envolvidas
banco/migração, serviço, aplicação (rotas), frontend (templates + subnav do ficha_layout), teste.

## Fora desta fatia
- Botão "marcar como realizada" na agenda (que puxaria data/treino da sessão agendada) — fatia futura.
- Esforço percebido (RPE) e vínculo ao treino do dia — ficaram fora (escolha do PO pelo modelo enxuto).
- Remover a rota órfã `/alunos/{id}/feedback` — cleanup futuro.

## Status
concluída
