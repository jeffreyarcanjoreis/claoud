# SPEC — Sistema Kairos (plataforma do coach)

> Fatia atual: **Treino** (fatia 9) — **completa** (9.1 biblioteca, 9.2 montar treinos, 9.3 ligar à agenda).
> Fatias 1-8 concluídas; 324 testes verdes.
> Workflow: `App Kairos Movimento/10 - Workflow da Área do Coach.md`. Domínio: `09 - Modelo de Domínio.md`.

## Overview

A capacidade **Treino** liga três coisas: uma **biblioteca de exercícios** (o acervo partilhado), os **treinos / planilhas** de cada aluno (um treino nomeado composto de exercícios com séries/reps/carga), e a **ligação à agenda** — ao ver uma marcação, um botão abre o treino atribuído àquele dia. Ancorada nos dados reais do Marcos (planilha = divisão semanal dia → foco muscular + cardio).

Decisões (com o PO): (a) o botão abre **o treino atribuído** à marcação, não um log de execução (esse fica como evolução futura); (b) a ligação treino↔dia é **manual por marcação**; (c) o vínculo vive nas **sessões Kairos** (os eventos do Google Calendar são só-leitura).

## Áreas

- **Treinos** (`/treinos`) — biblioteca de exercícios (lista + `/treinos/novo`).
- **Treino do aluno** (`/alunos/{id}/treino`) — sub-aba da ficha: os treinos do aluno; `/novo`; `/{treino_id}` mostra a planilha e permite adicionar/remover exercícios e apagar o treino.
- **Agenda** (`/alunos/{id}/agenda/nova`, `/alunos/{id}/agenda`, `/agenda`) — a marcação pode apontar para um treino; a agenda do aluno e a global de hoje mostram-no com link "ver treino".

## Comportamentos

**9.1 Biblioteca**
1. Separador "Treinos" → `/treinos`, biblioteca ordenada por nome (case-insensitive), botão "Adicionar exercício"; estado vazio.
2. Criar exercício com nome válido grava e lista; sem nome → recusa, valores preservados. Grupo/observação vazios → NULL / "sem registro".

**9.2 Montar treinos (planilha)**
3. Sub-aba "Treino" na ficha lista os treinos do aluno (com nº de exercícios) e tem "Novo treino"; estado vazio.
4. Criar treino com nome válido grava e redireciona à sua planilha; sem nome → recusa.
5. Na planilha, adicionar um exercício da biblioteca (com séries/reps/carga opcionais) junta-o em ordem; séries deve ser positivo se dado; escolher nenhum exercício → recusa.
6. Remover um exercício e apagar o treino inteiro (com verificação de dono: 404 ao aceder à planilha/item de outro aluno ou de outro treino).

**9.3 Ligar à agenda (o botão)**
7. O formulário de agendar oferece um select "Treino" com os treinos do aluno (opcional).
8. Agendar com um treino associa-o à sessão; um treino de outro aluno, ou um id inválido, é recusado.
9. A agenda do aluno e a agenda global de hoje (`/agenda`) mostram o nome do treino da sessão com um link "ver treino" para a planilha.
10. Uma sessão sem treino grava treino_id NULL (rule 6); nada muda para as sessões antigas.

**Geral**
11. Os 298 testes anteriores continuam verdes; nenhum comportamento anterior muda.

## Fora desta fatia

- Log de execução (o que foi realmente feito nesse dia: cargas/reps reais) — evolução futura sobre o vínculo.
- Divisão semanal automática (dia da semana → treino) que preencha a agenda sozinha.
- Editar um exercício da biblioteca ou um item do treino (por agora: remover + adicionar de novo).
- Vocabulário controlado de grupos musculares / filtro; vídeo/imagem do exercício.
