# SPEC — O arco da sessão (tempo por fase)

> Norte: o "mapa de tempo" das 5 fases do método (skill `kairos-method`, `references/pratica.md` §1). Dá à sessão a dimensão **tempo** que faltava.
> Base: trilha Treino concluída (fases + variações + execução + anexo + feedback); **1093 testes**, head de migração **0031**. Próxima camada por cima: periodização (macro/meso/micro) — fatia futura.

## Overview

Hoje o Treino mostra as 5 fases, mas **sem tempo** — e o tempo é o coração do método (*kairos* = o momento certo; *chronos* = o relógio). Esta feature dá a uma sessão uma **duração** (30/45/60 min) e desenha as 5 fases como um **arco visual** com os minutos proporcionais de cada fase, na planilha do coach e na página do aluno. Princípio do método: **"estrutura fixa, proporções vivas"** — os minutos default vêm da tabela canônica; ajustá-los ao momento é fatia futura. Regra 6: sessão sem duração = "sem arco definido" — nunca inventar minutos.

## Vocabulário fixo — o mapa de tempo (método)

As 5 fases e seus minutos por duração (proporção fixa; `references/pratica.md` §1):

| Fase | Pergunta-guia | 30 min | 45 min | 60 min |
|------|---------------|:---:|:---:|:---:|
| Preparação | Quem chegou hoje? | 3 | 4 | 5 |
| Aquecimento | O corpo está aqui agora? | 5 | 7 | 9 |
| Skill | Este corpo está pronto? | 7 | 11 | 15 |
| Ápice | Qual o limite de hoje? | 10 | 16 | 22 |
| Volta à calma | O que mudou? | 5 | 7 | 9 |

"Estrutura fixa; proporções vivas": ansioso pede mais preparação/aquecimento; radiante pede mais skill/ápice (o ajuste é [F+]).

## Áreas

- **Planilha do treino (coach)** — `/alunos/{id}/treino/{treino_id}` — o coach define a duração da sessão; o arco aparece acima/junto das fases.
- **Treino do aluno** — `/aluno/treinos/{treino_id}` — o aluno vê o arco (read-only) no topo do treino.

## Componentes

- **Arco da sessão** — faixa visual das 5 fases em segmentos proporcionais ao tempo, cada segmento com fase + pergunta-guia + minutos. Reusado nos dois lados (coach e aluno). Sem duração → não aparece (regra 6).
- **Seletor de duração (coach)** — 30 / 45 / 60 min (ou limpar).

## Comportamentos

### 1. Duração da sessão
1. **[F1]** O coach define a duração de um treino: **30**, **45** ou **60** min; pode **limpar** (volta a "sem arco").
2. **[F1]** Dado a duração, as 5 fases recebem os minutos da **tabela canônica** do método (nunca inventados; derivados, não digitados).

### 2. O arco visível
3. **[F1]** Na planilha do coach, o arco aparece: as 5 fases como segmentos proporcionais ao tempo, cada um com fase, pergunta-guia e minutos. Sem duração → sem arco (um convite discreto a definir a duração).
4. **[F1]** Na página do treino do aluno, o mesmo arco aparece **read-only** no topo.

### 3. Proporções vivas e ajuste
5. **[F1]** O coach ajusta os minutos de cada fase (override por fase), com a soma = duração — "proporções vivas". Trocar a duração reseta ao padrão; cada fase permanece (mín. 1 min).
6. **[F+]** Duração livre (além de 30/45/60), com proporções escaladas.
7. **[F+]** Ajuste ao momento: o arco reage ao check-in do aluno (dia de estresse alto sugere mais preparação/aquecimento).
8. **[F+]** Timer / sessão guiada ao vivo (conduzir fase a fase, no tempo).

### Geral
9. **[F1]** Toda escrita loga (regra 8); textos pt-BR; sem duração = "sem arco definido" (regra 6 — nunca minutos inventados). Os **1093 testes** anteriores seguem verdes; treinos existentes seguem funcionando (sem duração, sem arco).

## Fora do escopo (por ora)
- **Periodização** (macro/meso/micro) — a camada por cima das sessões (mesociclos com foco, microciclos, o arco da jornada). Fatia própria, logo a seguir.
- Timer / sessão guiada ao vivo e o ajuste automático ao check-in (comportamentos 7–8).
