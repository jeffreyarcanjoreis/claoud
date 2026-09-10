# SPEC — Sistema Kairos (plataforma do coach + área do aluno)

> Fatia atual: **Frente + nível autorreconhecido** (1ª fatia da profundidade do Treino).
> Primeira fatia que faz o app começar a *ser* Kairos: traz a frente e o nível do método para dentro do produto, com o nível **autodeterminado pelo aluno** (architecture.md, regras 11–14).
> Fatias anteriores entregues até a Fase 3; **786 testes**, head de migração **0022**. As 7 issues da Autoavaliação (Fase 4) ficam **paradas** em `issues/` para retomar depois.
> Método: skill `kairos-method`. Roadmap da área do aluno: `docs/roadmap-area-aluno.md`.

## Overview

Hoje o Treino é uma planilha plana — não carrega o método. Esta fatia traz duas ideias centrais do Kairos para dentro do produto: a **frente** (o arco de cada pessoa: Performance, Saúde Integrada ou Longevidade) e o **nível** (I–IV) dentro dessa frente. A frente nasce da avaliação inicial, então é o **coach** quem a define/ajusta na ficha; o nível é **autodeterminado** — quem se reconhece num nível é o **aluno**, que pode rever quando sentir. O coach vê o que o aluno reconheceu e acompanha (conscientiza, acolhe, respeita, educa), mas **nunca dá o nível**. É uma capacidade de dois lados, coach-primeiro para a frente.

## Vocabulário fixo (o conteúdo do método)

**Frentes** (uma principal por aluno nesta fatia):
- **Performance** — o corpo agora: técnica → picos de atleta.
- **Saúde Integrada** — o corpo equilibrado: criar hábito → saúde como identidade.
- **Longevidade** — o corpo no tempo longo: mobilidade/segurança → vitalidade plena para a idade.

**Níveis** (os mesmos quatro em qualquer frente; textos em 1ª pessoa para o aluno):
- **I · Fundação** — "aprendo a sentir, domino o simples."
- **II · Construção** — "amplio a capacidade, com domínio crescente."
- **III · Domínio** — "tenho autonomia, refino, encaro desafios reais."
- **IV · Maestria** — "alta capacidade e autorregulação — quase me conduzo."

## Áreas

- **Ficha do aluno → Frente (coach)** (`/alunos/{id}/...`) — o coach vê a frente atual do aluno e a define/ajusta entre as três; vê (só leitura) o nível que o aluno reconheceu, o histórico e as notas.
- **Meu Treino → Frente e nível (aluno)** (`/aluno/...`) — o aluno vê a sua frente e o que ela significa; se reconhece num nível I–IV (1ª pessoa), com nota opcional, revisável; e vê o histórico dos próprios reconhecimentos.

## Componentes

- **Seletor de frente** (coach) — as três frentes como opções; mostra a atual ou "sem registro".
- **Cartão de frente** (aluno) — a frente e seu significado, só leitura.
- **Reconhecimento de nível** (aluno) — os quatro níveis descritos em 1ª pessoa, o atual marcado como "me reconheço aqui", com nota opcional.
- **Linha do tempo de reconhecimentos** — histórico (data, nível, nota), mais recente primeiro; reusada no aluno e (leitura) no coach.

## Comportamentos

**Frente (coach-primeiro)**
1. Na ficha do aluno, o coach vê a frente atual do aluno, ou "sem registro" quando não há nenhuma.
2. O coach define a frente do aluno escolhendo uma das três; grava e passa a exibir a frente escolhida.
3. O coach troca a frente por outra das três; a atualização substitui a anterior (uma frente principal por aluno).
4. Uma frente fora do conjunto das três é recusada; nada é gravado.

**Nível (autodeterminado pelo aluno)**
5. Na sua área, o aluno vê a sua frente e o significado dela; sem frente definida, vê "sem registro" e um convite a falar com o coach (nada é inventado).
6. O aluno vê os quatro níveis descritos em 1ª pessoa e pode se reconhecer em um deles.
7. Reconhecer-se num nível grava um reconhecimento com a data e passa a mostrá-lo como "onde me reconheço hoje".
8. O aluno pode rever o seu nível a qualquer momento; o novo reconhecimento passa a ser o atual (o anterior fica no histórico).
9. Ao se reconhecer, o aluno pode deixar uma nota opcional do porquê; nota vazia fica NULL (regra 6).
10. O aluno vê o histórico dos próprios reconhecimentos (data, nível, nota), mais recente primeiro; vazio quando ainda não se reconheceu.
11. Isolamento: o aluno só vê e só registra o próprio nível (aluno_id da sessão); nunca o de outro.

**Coach acompanha (não dá nota)**
12. Na ficha, o coach vê o nível atual que o aluno reconheceu, o histórico e as notas — só leitura; "sem registro" quando o aluno ainda não se reconheceu. Em nenhum lugar o coach define o nível.

**Geral**
13. Sem frente / sem nível = "sem registro", nunca um default falso (regra 6). Texto do aluno em 1ª pessoa; o coach como presença, não régua (regras 11–14). Toda escrita loga; textos pt-BR. Os 786 testes anteriores continuam verdes; nada anterior muda.

## Fora desta fatia

- **Frente secundária** e as frentes futuras **Reabilitação** / **Bem-estar**.
- **Conscientização ativa do coach sobre o nível** (comentar/sugerir no reconhecimento) — nesta fatia o coach só lê; conversa vai pelo canal de mensagens que já existe.
- **Critérios/gate de passagem de nível** (os 4 critérios do método, marcadores Kairos) — aqui o reconhecimento é livre e revisável, sem gate.
- **Periodização** (macro/meso/micro), **as 5 fases da sessão** e **vídeo no exercício** — fatias seguintes da profundidade do Treino.
