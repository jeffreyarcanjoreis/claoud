# Issue 25 — Teste de fluxo funcional (ponta a ponta) + tarefa pós-treino automática + cenário demo

## Status
concluída

## Contexto / decisão do PO
Nesta fase funcional, provar que TODAS as funções do app se conectam de verdade,
percorrendo o fluxo real do coach: lead chega → vira aluno → entra no financeiro →
tem avaliação, treino e sessões marcadas → tarefa de contato no dia seguinte ao
treino → acompanhamento. O PO decidiu: (1) **construir** a automação da tarefa
pós-treino; (2) entregar **os dois formatos** — um teste automático de ponta a ponta
na suíte E um comando que popula um aluno-demo completo pra ver ao vivo.

---

## PARTE A — Tarefa "Contatar <aluno>" automática no dia seguinte ao treino (feature)
Ao marcar uma sessão (treino), o app cria automaticamente uma Tarefa de contato pro
dia seguinte.
- Gancho em `kairos/agenda/service.py::create_sessao`: depois de persistir a sessão,
  busca o nome do aluno (já usa `Aluno` no módulo) e cria uma Tarefa via
  `kairos.tarefas.service.create_tarefa` (import local pra deixar clara a direção
  agenda→tarefas; sem ciclo — tarefas não importa agenda):
  - `titulo = "Contatar {nome do aluno}"`
  - `categoria = "contato"`
  - `prazo = data da sessão + 1 dia` (ISO)
- Best-effort após o commit da sessão (a sessão é a fonte; a tarefa é conveniência).
- Decisões/limites (regra 6, sem exagero): uma tarefa por sessão criada; cancelar a
  sessão NÃO remove a tarefa (sem FK tarefa↔sessão) — anotado como refinamento futuro.
- Testes: criar uma sessão gera a tarefa certa (titulo com o nome, categoria contato,
  prazo = data+1); a tarefa aparece em `list_tarefas_abertas`.

## PARTE B — Teste de ponta a ponta (`tests/test_fluxo_completo.py`)
Um teste (ou poucos, bem nomeados) que percorre o funil inteiro via TestClient +
serviços, com asserção em cada elo:
1. **Lead chega**: `POST /comecar` (cadastro público, com consentimento) → a lead
   aparece em `list_contatos_abertos` / no Início.
2. **Vira aluno**: `POST /contatos/{id}/converter` → cria o Aluno com o perfil
   mapeado (contato/sexo/idade/objetivo/saúde) e a lead sai da caixa (virou_aluno).
3. **Financeiro**: define plano do aluno (`set_plano`) + registra um pagamento
   (`registrar_pagamento`) → `panorama_mes`/`resumo_financeiro` refletem (MRR,
   recebido, "quem sustenta o mês" inclui o aluno).
4. **Avaliação**: cria uma avaliação pro aluno → aparece no histórico dele.
5. **Treino**: cria um treino (planilha) + adiciona um item (exercício).
6. **Agenda + automação**: agenda uma sessão com esse treino → a sessão aparece na
   agenda do aluno E a **tarefa "Contatar <aluno>" do dia seguinte** foi criada
   (Parte A) e aparece nas tarefas abertas.
7. **Acompanhamento**: registra uma sessão realizada → aparece no histórico.
8. Asserção final de coerência: o aluno está nas listagens; o financeiro do mês o
   inclui; a tarefa existe com o prazo certo. (Isolamento KAIROS_DATA_DIR tmp +
   dispose_engine, como os demais testes.)

## PARTE C — Cenário demo pra ver ao vivo (CLI)
Comando no `kairos/cli.py` que popula um aluno-demo completo no banco de
desenvolvimento, pra você abrir o app e navegar:
- `python -m kairos.cli semear-demo` → roda migrações e cria: a lead (via cadastro)
  → converte em aluno (nome claramente de demo, ex. **"Ana Demonstração"**), define
  plano + pagamento do mês, cria uma avaliação, um treino com itens, agenda 1–2
  sessões (que disparam as tarefas de contato), e registra uma sessão realizada.
  Ao fim, imprime um resumo com os caminhos pra conferir (`/alunos/{id}`,
  `/financeiro`, `/agenda`, Início).
- `python -m kairos.cli semear-demo --remover` → remove SÓ os dados de demo
  (pelo nome/marcação de demo), preservando dados reais.
- **Proteção de dados reais** (crítico): o comando NUNCA toca em Aluno "Marcos
  Anastasio" nem no Contato "jeffrey reis"; opera só sobre a marcação de demo. Se já
  existir a demo, `--remover` limpa antes de recriar (idempotente).

## Testes (teste-writer)
- Parte A: cobertura da tarefa automática (unit no serviço de agenda).
- Parte B: o `test_fluxo_completo.py`.
- Rodar a suíte inteira; reportar verde. (SEM migração — nenhuma coluna nova.)

## Verificação no navegador
Rodar `semear-demo`, abrir o app e conferir o aluno-demo em Alunos, o financeiro do
mês, a agenda com a sessão, e a tarefa "Contatar Ana Demonstração" no Início; depois
`--remover` pra limpar.

## Fora de escopo
- Remover a tarefa automática ao cancelar a sessão (refinamento futuro).
- Notificações/lembretes de verdade (e-mail/WhatsApp) — a tarefa é interna.

## Camadas / subagentes
servico-writer (Parte A: gancho no create_sessao) → cli-writer (Parte C: semear-demo)
→ teste-writer (Partes A e B: testes + suíte). Sem banco-migracao, sem frontend novo.
