# Roadmap — Área do Aluno (Kairos)

Sequenciamento de construção da **Área do Aluno**, a partir da spec das 7 telas
(00 Bem-vindo · 01 Perfil · 02 Treinos · 03 Avaliações · 04 Newsletter · 05
Financeiro · 06 Agenda). Este documento é o **como e em que ordem**; a spec é o
**o quê**.

## Princípios que governam a ordem

1. **A área do aluno é read-only, abastecida pelo coach** (a própria spec diz isso em
   toda tela). Então, para o aluno **ver** algo, o **coach precisa produzir** aquilo
   primeiro — em modelo e em tela. **Coach-primeiro** é a regra de sequência.
2. **Regra 6 (dados nunca inventados):** nada de telas com dado de mentira/placeholder.
   Uma tela só entra quando existe dado real por trás.
3. **Regra de ouro da spec:** todo input do aluno tem que mudar algo visível e/ou
   voltar pro coach. As **5 válvulas** (check-in, pós-sessão, sinal de saúde,
   autoavaliação, confirmação de agenda) são o que impede o app de virar catálogo
   morto — são prioridade de valor, mas são features de **dois lados**.
4. **Uma fatia de cada vez**, no fluxo `/plan → aprovação → /execute`.

## Estado atual (setembro/2026)

Já construído e no ar (Supabase/Postgres, login multiusuário, migração head 0019):

- **Modelos existentes:** Aluno (dados gerais + saúde + email), Avaliação (+ Perimetria
  + gráfico), Exercício, Treino, TreinoItem (planilha plana), SessãoAgendada,
  SessãoRealizada (presença/disposição/feedback), PlanoAluno, Pagamento, Contato,
  Tarefa, Despesa, Perfil (auth).
- **Área do aluno hoje (`/aluno`, Fases 3.1/3.2):** landing com próximos
  agendamentos, meus treinos (+detalhe read-only), minhas avaliações (+detalhe),
  histórico de sessões. Gate por papel, link de ativação, esqueci-senha.
- **Lado do coach:** painel completo (alunos, avaliações, treinos, agenda, financeiro,
  acompanhamento, tarefas, contatos/leads, vitrine).

## As 7 telas × o que já existe

| Tela | Já dá pra espelhar (coach produz) | Falta (capacidade nova) |
|---|---|---|
| 00 Bem-vindo | atalhos, próxima sessão | check-in, treino-que-reage, pulso Kairos, recado do coach |
| 01 Perfil | dados gerais + saúde (dele) | frente/nível, Ficha A/B (história/intenção), cidade, toggles de privacidade, conta (idioma/tema/notif), export RGPD, sinal de dor |
| 02 Treinos | planilha atual + histórico | ciclo (Macro/Meso/Micro), 7 dias, 5 fases, regressão/progressão, vídeo, sessão guiada, execução/RPE |
| 03 Avaliações | marcadores de base, perimetria, gráfico, linha do tempo | Marcadores Kairos, passagem de nível, autoavaliações |
| 04 Newsletter | — | área inteira (feed, 5 pilares, coleções, salvos, reações) |
| 05 Financeiro | plano + pagamentos (dele) | recibos, cartão salvo (provedor), checkout, renovar/upgrade |
| 06 Agenda | próximas sessões | marcar por disponibilidade, detalhe/preparação, presença, lembretes, sync |

## Fases (ordem recomendada)

### Fase 0 — Base do espelho 🟢 *(sobre dados que já existem — construir primeiro)*
**Objetivo:** uma área do aluno real e útil já, com tudo que o coach **já** produz.
- **Cobre:** 01 Perfil (dados + saúde dele, **sem** as notas internas Alerta/Observações),
  05 Financeiro (plano + pagamentos dele, sem os números do negócio), Acompanhamento
  com detalhe, e organizar a `/aluno` em seções/abas (como a ficha do coach). Treinos,
  Avaliações e Agenda já existem — entram na organização.
- **Coach-primeiro:** nada novo — o coach já produz tudo isso.
- **Modelos novos:** nenhum. Sem migração. Reaproveita os serviços existentes.
- **Tamanho:** médio. **Entrega 5 das 7 telas na versão do que dá hoje.**

### Fase 1 — Contato com o coach 🟡 *(1ª válvula de vínculo)*
**Objetivo:** o "Recado do coach" (tela 00) + canal aluno↔coach.
- **Modelo novo:** `Mensagem` (aluno_id, autor coach|aluno, texto, lida, created_at;
  áudio fica pra depois).
- **Dois lados:** coach vê/responde (na ficha do aluno ou numa caixa de entrada);
  aluno vê o recado + responde.
- **Tamanho:** médio. Resolve o vínculo entre sessões (o ponto mais frágil no digital).

### Fase 2 — Check-in diário 🟡 *(a válvula-assinatura do método)*
**Objetivo:** tela 00 ganha vida — o aluno registra o estado, o coach lê.
- **Modelo novo:** `CheckinDiario` (aluno_id, data, sono h+qualidade, estresse,
  energia, humor, dor: mapa+intensidade).
- **Dois lados:** aluno registra (editável até o fim do dia); coach lê no painel.
- **Elo crítico (spec):** o card "treino de hoje" precisa **reagir** ao check-in.
  *v1 honesto:* registrar + o coach ler + uma nota simples; a **reconfiguração
  automática** do treino é refinamento posterior (depende da Fase 5).
- **Tamanho:** médio.

### Fase 3 — Execução do treino + registro pós-sessão 🟡 *(válvula: o que mudou)*
**Objetivo:** fechar o ciclo do dia — o aluno executa e registra.
- **Modelo novo:** log de execução (carga/reps feitas por série, RPE, "feito", dor
  nova) ligado ao treino/dia. (Era marcado como "evolução futura" na SPEC original.)
- **Dois lados:** alimenta a leitura da próxima sessão pelo coach.
- **Depende de:** planilha atual (existe). Sessão guiada com timer/fases só na Fase 5.
- **Tamanho:** médio.

### Fase 4 — Autoavaliações + Marcadores Kairos + passagem de nível 🟡
**Objetivo:** medir o que o mercado não mede (tela 03 completa).
- **Modelos novos:** `Autoavaliacao` (questionário enviado pelo coach + respostas),
  `MarcadorKairos` (presença/autorregulação/autonomia por período), e o conceito de
  **frente + nível I–IV**.
- **Dois lados:** coach envia questionário e reconhece passagem de nível; aluno
  responde e vê a evolução.
- **Tamanho:** grande (introduz o modelo de níveis/frentes do método).

### Fase 5 — Periodização + fases da sessão + sessão guiada 🔴 *(épico profundo)*
**Objetivo:** o treino deixa de ser planilha plana e vira **ciclo** (tela 02 completa).
- **Modelos novos:** Macro/Meso/Micro, 7 dias da semana, 5 fases da sessão,
  regressão/progressão por exercício, `video_url` no exercício (era fatia curta
  planejada), sessão guiada com timer/áudio.
- **Coach-primeiro:** o coach precisa planejar ciclos (grande mudança no lado dele).
- **Tamanho:** grande. É a reescrita do coração operacional.

### Fase 6 — Newsletter / Conteúdo & Comunicação 🔴 *(área nova inteira)*
**Objetivo:** vínculo e filosofia entre sessões (tela 04); preenche a área
"Conteúdo & Comunicação" (hoje "em breve") do coach.
- **Modelos novos:** `Conteudo` (pilar, tipo valor/conexão/conversão, corpo, mídia),
  coleções, salvos, reações/comentários.
- **Dois lados:** coach publica (ritmo 3-2-1 pelos 5 pilares); aluno lê/salva/reage.
- **Tamanho:** grande. Independente das outras — pode subir de posição se o funil
  da marca for prioridade.

### Fase 7 — Agenda self-service + lembretes + sync 🔴
**Objetivo:** o aluno marca dentro da disponibilidade do coach (tela 06 completa).
- **Modelos novos:** `Disponibilidade` (janelas do coach); marcação/confirmação/
  remarcação com política; lembretes (precisa de notificações); export iCal.
- **Coach-primeiro:** o coach define janelas e política.
- **Tamanho:** grande.

### Fase 8 — Gateway de pagamento 🔴 *(integração externa)*
**Objetivo:** recibos, cartão salvo, checkout, renovar/upgrade (tela 05 completa).
- **Integração:** provedor (Stripe/afins) — recibos, meio de pagamento, checkout.
- **Depende de:** hospedagem + chaves; decisão de negócio. Hoje o financeiro é
  registro manual.
- **Tamanho:** grande.

## Cross-cutting (entram distribuídos, não como fase única)
- **Estados do aluno** (Acolhimento / Ativo / Pausado / Passagem) — cada tela se adapta.
- **Conta & preferências** (idioma PT-BR/PT-PT, tema, notificações) e **privacidade**
  (toggles de consentimento granulares) — pedaços em Perfil (Fase 0/1).
- **Export RGPD/LGPD** dos dados do aluno.
- **Notificações** (base pros lembretes, recado, "novo" na newsletter).

## As 5 válvulas (prioridade de valor)
1. Check-in diário → **Fase 2**
2. Registro pós-sessão → **Fase 3**
3. Sinal de saúde (nova dor/lesão) → pode entrar já na **Fase 0/1** (campo no Perfil
   que gera alerta pro coach — barato e alto valor)
4. Autoavaliação → **Fase 4**
5. Confirmação de agenda → **Fase 7** (uma versão simples de "confirmar presença"
   pode entrar antes, junto da Fase 0, já que a agenda existe)

## Sequência recomendada (resumo)
**0 (base) → 1 (contato) → 2 (check-in) → 3 (execução) → 4 (autoaval/nível) →
5 (periodização) → 6 (newsletter) → 7 (agenda self-service) → 8 (pagamento).**

Fases 6–8 são as mais independentes e podem ser reordenadas por prioridade de negócio
(ex.: newsletter antes, se o funil da marca pesar mais).

## Vitórias rápidas que dá pra encaixar cedo (baratas, alto valor)
- **Sinal de dor/lesão** no Perfil (válvula 3) → alerta pro coach.
- **Confirmar presença** na agenda (parte da válvula 5) → a agenda já existe.
- **Vídeo do exercício** (`video_url`, links YouTube) → decidido há tempo, fatia curta.
