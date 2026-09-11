# SPEC — Sistema Kairos (plataforma do coach + área do aluno)

> Fatia atual: **As 5 fases da sessão — organizar a planilha do treino** (profundidade do Treino).
> Recorte enxuto: cada exercício do treino pertence a uma das 5 fases; a planilha (coach e aluno) passa a mostrar os exercícios agrupados nas fases, cada uma com sua pergunta-guia.
> Fatia anterior (Frente + nível) concluída; **826 testes**, head de migração **0024**. As 7 issues da Autoavaliação (Fase 4) seguem paradas em `issues/parked/`.
> Método: skill `kairos-method` (as 5 fases estão em `references/pratica.md`). Roadmap: `docs/roadmap-area-aluno.md`.

## Overview

Hoje o treino de um aluno é uma **planilha plana** — uma lista de exercícios sem estrutura. Esta fatia traz a primeira camada do método para dentro dela: as **5 fases da sessão**. Cada exercício passa a pertencer a uma fase (Preparação → Aquecimento → Skill → Ápice → Volta à calma); o coach escolhe a fase ao montar o treino, e a planilha — do coach e do aluno — passa a se ler como uma **sessão em fases**, cada uma com a sua pergunta-guia, em vez de uma lista solta. É a estrutura fixa do método aparecendo no produto (proporções/tempos e ajuste ao momento vêm depois).

## Vocabulário fixo (as 5 fases, do método)

Ordem canônica, cada fase com a sua pergunta-guia:

1. **Preparação** — "Quem chegou hoje?"
2. **Aquecimento** — "O corpo está aqui agora?"
3. **Skill** — "Este corpo está pronto?"
4. **Ápice** — "Qual o limite de hoje?"
5. **Volta à calma** — "O que mudou?"

Um exercício sem fase definida (inclusive os de treinos já existentes) aparece num grupo **"Sem fase"** ao fim — nunca numa fase inventada (regra 6).

## Áreas

- **Planilha do treino (coach)** (`/alunos/{id}/treino/{treino_id}`) — ao adicionar um exercício, o coach escolhe a fase; a planilha mostra os exercícios agrupados nas 5 fases (ordem canônica, com a pergunta-guia), mais o grupo "Sem fase" quando houver.
- **Treino do aluno (leitura)** (`/aluno/treinos/{treino_id}`) — a mesma planilha, agrupada nas 5 fases com as perguntas-guia, só leitura.

## Componentes

- **Seletor de fase** — as 5 fases como opções no formulário de adicionar exercício (mais "—" para sem fase).
- **Bloco de fase** — cabeçalho com o nome da fase + a pergunta-guia, seguido dos exercícios daquela fase (ou "nenhum exercício nesta fase"); reutilizado na planilha do coach e na do aluno.

## Comportamentos

**Montar (coach)**
1. Ao adicionar um exercício ao treino, o coach pode escolher a fase dele entre as 5 (ou deixar sem fase).
2. Adicionar um exercício com uma fase válida grava o exercício naquela fase; uma fase fora do conjunto das 5 é recusada (nada gravado).
3. Adicionar um exercício sem escolher fase grava-o sem fase (NULL / "Sem fase"), sem inventar.

**Ver a planilha em fases (coach)**
4. A planilha do treino do coach mostra os exercícios agrupados nas 5 fases, sempre na ordem canônica, cada fase com o seu nome e a sua pergunta-guia.
5. Uma fase sem exercícios aparece com "nenhum exercício nesta fase"; exercícios sem fase aparecem num grupo "Sem fase" ao fim (omitido quando não há nenhum).

**Ver a planilha em fases (aluno)**
6. A planilha do treino do aluno mostra os mesmos exercícios agrupados nas 5 fases, na ordem canônica, cada fase com a sua pergunta-guia (só leitura).

**Geral**
7. Dentro de cada fase, os exercícios mantêm a ordem em que foram adicionados. Trocar a fase de um exercício é remover e adicionar de novo (mesmo padrão atual do treino — sem edição in-place nesta fatia).
8. Toda escrita loga; textos pt-BR; campo sem dado = "Sem fase" (regra 6). Os 826 testes anteriores continuam verdes; nenhum comportamento anterior muda (treinos existentes seguem funcionando, com seus exercícios em "Sem fase").

## Fora desta fatia

- **Tempos / proporção por fase** (ex.: 45min → 4/7/11/16/7) e o **ajuste ao momento** (a sessão que reage ao check-in).
- **Timer / sessão guiada** (conduzir a sessão fase a fase no app).
- **Editar a fase de um item in-place** (por ora: remover + adicionar).
- **Vídeo no exercício** e **periodização** (macro/meso/micro) — fatias seguintes da profundidade do Treino.
