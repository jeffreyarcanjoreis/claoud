# SPEC — Treino do aluno (profundidade completa)

> Norte: o mockup aprovado da página de Treino do aluno. Descreve o Treino **inteiro**; construído em fatias pequenas.
> **Fatia atual (1): Estrutura da planilha** — 5 fases + apresentação do treino + observação por exercício. As demais capacidades (4–8) são fatias futuras, já mapeadas aqui para dar o norte.
> Base: fatia Frente + nível concluída; **826 testes**, head de migração **0024**. Método: skill `kairos-method` (`references/pratica.md`).

## Overview

Hoje o treino do aluno é uma **planilha plana** — lista de exercícios sem estrutura nem vida. Esta feature transforma o Treino na **sessão do método**: os exercícios organizados nas 5 fases (cada uma com sua pergunta-guia), com apresentação do coach, vídeo, níveis, observações, execução registrada pelo aluno e feedback do coach sobre o que foi enviado. Dois lados: o **coach monta** a planilha; o **aluno vê e executa**. Coach-primeiro. Construído em fatias — a 1ª entrega a **estrutura** (fases + apresentação + observação por exercício), aproveitando o que já existe no banco.

## Vocabulário fixo (as 5 fases da sessão)

Ordem canônica, cada fase com a sua pergunta-guia:
1. **Preparação** — "Quem chegou hoje?"
2. **Aquecimento** — "O corpo está aqui agora?"
3. **Skill** — "Este corpo está pronto?"
4. **Ápice** — "Qual o limite de hoje?"
5. **Volta à calma** — "O que mudou?"

Exercício sem fase = grupo **"Sem fase"** ao fim (nunca uma fase inventada — regra 6).

## Áreas

- **Planilha do treino (coach)** — `/alunos/{id}/treino/{treino_id}` — o coach monta: adiciona exercícios (com fase, séries/reps/carga, observação), edita, reordena, escreve a apresentação; futuramente vê a execução e o vídeo enviados pelo aluno e dá feedback.
- **Treino do aluno** — `/aluno/treinos/{treino_id}` — o aluno vê a planilha como sessão em fases; futuramente escolhe o nível, marca feito, registra o que fez, anexa vídeo e lê o feedback.
- **Biblioteca de exercícios (coach)** — `/treinos` — o acervo compartilhado; futuramente com vídeo de demonstração por exercício.

## Componentes

- **Bloco de fase** — cabeçalho (nome + pergunta-guia) + os exercícios daquela fase (ou "nenhum exercício nesta fase"); reusado na planilha do coach e do aluno.
- **Card de exercício** — nome, prescrição (séries/reps/carga), observação; cresce nas fatias futuras com vídeo, níveis, execução e feedback.
- **Seletor de fase** — as 5 fases (+ "—") no formulário de adicionar exercício.
- **Apresentação** — o texto do coach no topo do treino.

## Comportamentos

Marcador: **[F1]** = fatia atual (estrutura); **[F+]** = fatia futura (mapeada para o norte).

### 1. Estrutura em fases
1. **[F1]** Ao adicionar um exercício ao treino, o coach pode escolher a fase dele entre as 5 (ou deixar sem fase).
2. **[F1]** Adicionar com uma fase válida grava o exercício naquela fase; uma fase fora do conjunto é recusada (nada gravado).
3. **[F1]** A planilha do coach mostra os exercícios agrupados nas 5 fases, na ordem canônica, cada fase com o seu nome e a sua pergunta-guia.
4. **[F1]** Uma fase sem exercícios aparece com "nenhum exercício nesta fase"; exercícios sem fase aparecem no grupo "Sem fase" ao fim (omitido quando não há nenhum).
5. **[F1]** A planilha do aluno mostra os mesmos exercícios agrupados nas 5 fases, na ordem canônica, com as perguntas-guia (só leitura).
6. **[F1]** Dentro de cada fase, os exercícios mantêm a ordem em que foram adicionados.

### 2. Apresentação do treino
7. **[F1]** O coach escreve/edita a apresentação do treino (um texto de enquadramento); vazio = "sem registro" (regra 6).
8. **[F1]** O aluno vê a apresentação no topo do treino quando existe.

### 3. Observação por exercício (coach)
9. **[F1]** Ao adicionar um exercício, o coach pode escrever uma observação para aquele item (ex.: "foco na postura").
10. **[F1]** A observação do exercício aparece na planilha do coach e na do aluno quando existe; vazia = não aparece.

### 4. Editar e reordenar (coach)
11. **[F+]** O coach edita séries/reps/carga/observação de um exercício in-place (sem remover e adicionar de novo).
12. **[F+]** O coach reordena os exercícios dentro de uma fase (mover para cima/baixo ou arrastar).
13. **[F+]** O coach move um exercício de uma fase para outra sem remover.

### 5. Vídeo do exercício (biblioteca)
14. **[F+]** Um exercício da biblioteca pode ter um vídeo de demonstração (link ou upload — decisão no /plan).
15. **[F+]** O vídeo aparece no card do exercício, na planilha do coach e do aluno.

### 6. Níveis por exercício
16. **[F+]** Um exercício do treino oferece base / regressão / progressão (o coach descreve as variações).
17. **[F+]** O aluno escolhe "meu lugar hoje" entre as variações (autodeterminado; regras 11–14); a escolha é dele, revisável.

### 7. Execução do aluno
18. **[F+]** O aluno marca um exercício como feito; o progresso da sessão reflete quantos foram feitos.
19. **[F+]** O aluno registra o que realmente fez (carga/reps reais) por exercício.
20. **[F+]** O aluno escreve uma observação da execução do exercício (o "verbo é dele").

### 8. Anexo da execução + feedback do coach
21. **[F+]** O aluno anexa um vídeo/foto da execução de um exercício para o coach analisar (precisa de armazenamento — decisão no /plan).
22. **[F+]** O coach vê o anexo enviado e deixa um feedback naquele exercício.
23. **[F+]** O aluno lê o feedback do coach no card do exercício.

### Geral
24. **[F1]** Toda escrita loga (regra 8); textos pt-BR; campo sem dado = "sem registro"/"Sem fase" (regra 6). Os 826 testes anteriores continuam verdes; treinos existentes seguem funcionando (exercícios em "Sem fase", sem apresentação).

## Fora do escopo (por ora)
- Tempos/proporção por fase (ex.: 45min → 4/7/11/16/7) e o **ajuste ao momento** (a sessão que reage ao check-in).
- **Timer / sessão guiada** (conduzir a sessão fase a fase, ao vivo).
- **Periodização** (macro/meso/micro) — o "arco" da Tela 1, fatia própria mais adiante.
