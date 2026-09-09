# SPEC — Sistema Kairos (plataforma do coach + área do aluno)

> Fatia atual: **Autoavaliação** (Fase 4 do roadmap da área do aluno) — a 4ª válvula.
> Fatias anteriores concluídas até a Fase 3 (registro pós-treino); **786 testes** (785 + 1 skip), head de migração **0022**.
> Roadmap: `docs/roadmap-area-aluno.md`. Workflow: `App Kairos Movimento/10 - Workflow da Área do Coach.md`. Domínio: `09 - Modelo de Domínio.md`.

## Overview

A **Autoavaliação** é a 4ª válvula do método (o aluno mede o que o mercado não mede) e o primeiro passo da Fase 4. O coach **envia** ao aluno uma autoavaliação — um questionário **fixo do método Kairos** (não é montado à mão nesta fatia) — e o aluno **responde** dando uma nota 0–10 a cada pergunta mais uma observação livre. O coach **lê** as respostas na ficha do aluno; os dois lados veem o histórico. É uma feature de dois lados, coach-primeiro: o coach precisa enviar antes de o aluno ter o que responder.

Decisões (com o PO): (a) o questionário é um **modelo fixo Kairos** — o coach só dispara, não escreve perguntas; editar o modelo fica fora desta fatia; (b) cada pergunta é uma **escala 0–10** (notas obrigatórias) mais **uma observação em texto livre** (opcional); (c) o coach envia **por aluno, sob demanda** (sem agendamento/recorrência); o aluno responde **uma vez** e a resposta passa a ser só-leitura; (d) o histórico (enviadas/respondidas) é visível para o aluno e para o coach.

## Modelo fixo Kairos (v1)

Cinco perguntas de escala **0–10** (o aluno se avalia no período), mais uma observação livre. Textos refináveis depois (fora desta fatia):

1. **Autorregulação** — "Consegui ajustar o esforço ao que meu corpo pedia."
2. **Autonomia** — "Me senti capaz de conduzir meus treinos sem depender de instrução o tempo todo."
3. **Consistência** — "Mantive a regularidade que combinei comigo."
4. **Conexão** — "Me senti presente e conectado durante o movimento."
5. **Evolução percebida** — "Senti evolução no meu corpo / condicionamento no período."
6. **Observação** (texto livre, opcional) — "O que mais você quer me contar sobre esse período?"

## Áreas

- **Autoavaliações do aluno (coach)** (`/alunos/{id}/autoavaliacoes`) — sub-aba da ficha: lista as autoavaliações enviadas àquele aluno (data, estado pendente/respondida) e o botão "Enviar autoavaliação"; abrir uma respondida mostra as notas + observação (só-leitura).
- **Autoavaliação (aluno)** (`/aluno/autoavaliacoes`) — nova aba na área do aluno: a(s) pendente(s) para responder + o histórico das respondidas; abrir uma pendente mostra o formulário; abrir uma respondida mostra as respostas (só-leitura).
- **Início do aluno** (`/aluno`) — ganha um CTA leve quando há autoavaliação pendente (eco da regra de ouro).

## Componentes

- **Cartão de autoavaliação** — item de lista com data e estado (pendente / respondida), reutilizado nas duas listas (coach e aluno).
- **Formulário do modelo Kairos** — as 5 escalas 0–10 + observação, renderizado no lado do aluno (resposta) e reusado como leitura no lado do coach.

## Comportamentos

**Envio (coach-primeiro)**
1. A sub-aba "Autoavaliações" na ficha do aluno lista as autoavaliações daquele aluno (data de envio, estado), mais recente primeiro; estado vazio quando não há nenhuma.
2. O botão "Enviar autoavaliação" cria uma nova autoavaliação para o aluno no estado **pendente** (com a data de envio) a partir do modelo fixo, e volta à lista mostrando-a.
3. Enviar quando o aluno já tem uma autoavaliação **pendente** é recusado com aviso (não empilha pendentes).

**Resposta (aluno)**
4. A aba "Autoavaliação" na área do aluno mostra a(s) pendente(s) para responder e o histórico das respondidas; estado vazio quando não há nenhuma.
5. Abrir uma autoavaliação pendente mostra o formulário do modelo Kairos: as 5 perguntas em escala 0–10 e o campo de observação.
6. Responder com as 5 notas válidas (0–10) grava as respostas, marca a autoavaliação como **respondida** (com a data de resposta) e redireciona à lista.
7. Uma nota fora de 0–10, ou uma nota faltando, é recusada sem perder o que já foi digitado (a observação é opcional).
8. Uma autoavaliação já **respondida** é só-leitura: mostra as respostas gravadas e não pode ser respondida de novo (novo envio de resposta é recusado).
9. Isolamento: o aluno só vê e só responde autoavaliações do próprio (aluno_id da sessão); abrir/responder a de outro aluno devolve "não encontrado" (404, nunca 403).

**Leitura (coach)**
10. O coach abre uma autoavaliação **respondida** e vê as notas por pergunta e a observação (só-leitura); uma **pendente** aparece como "aguardando resposta".

**Início (regra de ouro)**
11. Quando o aluno tem autoavaliação pendente, o início mostra um CTA leve "Você tem uma autoavaliação para responder → responder"; sem pendente, o CTA não aparece.

**Geral**
12. Toda escrita gera log; textos exibidos em português (regra 10); campo sem dado é NULL / "sem registro" (regra 6). Os 786 testes anteriores continuam verdes; nenhum comportamento anterior muda.

## Fora desta fatia (Fase 4 seguinte / futuro)

- **Marcadores Kairos** (presença / autorregulação / autonomia por período, avaliados pelo coach) — fatia seguinte da Fase 4.
- **Passagem de nível** — o conceito de **frente + nível I–IV** e o reconhecimento de subida de nível pelo coach — fatia seguinte da Fase 4.
- **Coach escrever/editar o questionário** (perguntas próprias, editar o modelo fixo).
- **Envio recorrente/agendado** e **notificações** de nova autoavaliação.
- Outros tipos de resposta (múltipla escolha); gráfico de evolução das notas ao longo do tempo.
- **Log de execução do treino** (cargas/reps reais por série — Fase 3b), independente desta fatia.
