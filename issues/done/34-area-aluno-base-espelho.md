# 34 — Área do aluno: base do espelho (Fase 0 do roadmap)

Fase 0 de [docs/roadmap-area-aluno.md](../docs/roadmap-area-aluno.md). Entrega uma
área do aluno organizada e útil sobre **os dados que o coach já produz** (read-only),
e vira a fundação onde as válvulas (Fases 1+) vão encaixar.

## Status
concluída

## Princípio
Tudo aqui é **read-only** e usa **sempre o `aluno_id` da sessão, nunca da URL**. Nas
telas de detalhe (id na URL), verifica dono → 404 se não for dele. Nada de dado
inventado (regra 6). **Não** mostra os campos internos do coach (`alert`, `notes`) nem
números do negócio (MRR etc.). Sem modelo/migração/serviço novo — reaproveita o que
existe.

## Especificação funcional

### Estrutura: home + sub-páginas + navegação
1. A `/aluno` deixa de ser uma página única com tudo empilhado e vira um **home** com:
   saudação ("Olá, {primeiro nome}"), **próxima sessão** (se houver) e **atalhos** para
   as áreas. (O home rico da spec — check-in, pulso, recado — é Fase 1/2; aqui é só a
   base honesta.)
2. Uma **navegação** própria do aluno (no `area_aluno/base.html`), com: Início, Perfil,
   Treinos, Avaliações, Agenda, Financeiro, Acompanhamento + **Sair**. Marca a aba ativa.
3. As listas que hoje moram no `inicio.html` (treinos, avaliações, agendamentos,
   histórico) **migram** para suas sub-páginas.

### Perfil `/aluno/perfil`
4. Mostra o retrato do aluno (dados dele): nome, foto (se houver), idade/idade
   informada, sexo, contato, e-mail, objetivo, frequência; e **Saúde**: condições,
   restrições/lesões, medicamentos, nível de condicionamento. Vazios = "sem registro".
   **NÃO** mostra `alert` nem `notes` (internos do coach). Read-only (editar é Fase 1+).
5. `GET /aluno/foto` serve a foto do próprio aluno (reaproveita o file-serving de
   `kairos/alunos/fotos.py`), ou 404 sem foto.

### Treinos `/aluno/treinos`
6. Lista os treinos do aluno (`list_treinos`) com link para a planilha
   `/aluno/treinos/{id}` (detalhe read-only **já existente**). Estado vazio honesto.

### Avaliações `/aluno/avaliacoes`
7. Lista as avaliações (`list_avaliacoes`) com link para o detalhe
   `/aluno/avaliacoes/{id}` (**já existente**). Estado vazio honesto.

### Agenda `/aluno/agenda`
8. **Próximas sessões** (de `list_sessoes`, data >= hoje) e o **histórico** (data <
   hoje), com treino associado quando houver. Read-only. Estados vazios honestos.

### Financeiro `/aluno/financeiro`
9. **Meu plano** (`get_plano`): formato (rótulo), valor (formatado), ciclo em meses,
   início. **Pagamentos** (`pagamentos_do_aluno`): competência (mês/ano), valor, data
   e status (pago/pendente). Sem indicadores do negócio. Estados vazios honestos.

### Acompanhamento `/aluno/acompanhamento`
10. Lista as sessões realizadas (`list_sessoes_realizadas`) e um **detalhe**
    `/aluno/acompanhamento/{id}` (`get_sessao_realizada`, **com verificação de dono →
    404**): data, presença (rótulo), disposição, feedback.

### Geral
11. Read-only em tudo; nenhuma rota de escrita sob `/aluno`. Gate já cobre `/aluno*`.
    Nenhum comportamento do coach muda. Sem migração/model/serviço.

## Pré-condições
- Fases 3.1/3.2 do login concluídas (sessão do aluno com `aluno_id`, gate por área).
- Serviços reaproveitados (todos já existem): `alunos.service.get_aluno`;
  `treinos.service.list_treinos`/`get_treino`/`get_treino_detail`;
  `avaliacoes.service.list_avaliacoes`/`get_avaliacao`/`get_avaliacao_detail`;
  `agenda.service.list_sessoes`; `financeiro.service.get_plano`/`pagamentos_do_aluno`;
  `acompanhamento.service.list_sessoes_realizadas`/`get_sessao_realizada`;
  `alunos.fotos` (serve foto); `web.formatar_reais`.

## Arquivos a criar
- `kairos/templates/area_aluno/perfil.html` — retrato + saúde (read-only).
- `kairos/templates/area_aluno/treinos.html` — lista de treinos (extraída do home).
- `kairos/templates/area_aluno/avaliacoes.html` — lista de avaliações (extraída).
- `kairos/templates/area_aluno/agenda.html` — próximas + histórico.
- `kairos/templates/area_aluno/financeiro.html` — plano + pagamentos.
- `kairos/templates/area_aluno/acompanhamento.html` — lista de sessões realizadas.
- `kairos/templates/area_aluno/acompanhamento_detalhe.html` — detalhe (read-only).
- `tests/test_area_aluno_base.py` — cobre itens 4–11, com foco em **isolamento**
  (aluno A não vê financeiro/acompanhamento/perfil de B; detalhe de outro → 404;
  `alert`/`notes` NUNCA aparecem no perfil) e na **navegação** (as abas existem).

## Arquivos a modificar
- `kairos/area_aluno/routes.py`:
  - `GET /aluno` vira o **home** (saudação + próxima sessão + atalhos), sem as listas.
  - novas rotas: `GET /aluno/perfil`, `/aluno/treinos`, `/aluno/avaliacoes`,
    `/aluno/agenda`, `/aluno/financeiro`, `/aluno/acompanhamento`,
    `/aluno/acompanhamento/{id}` (dono→404) e `GET /aluno/foto`.
  - helpers de display locais (datas, rótulos, `formatar_reais`); `aluno_id` sempre da
    sessão; import local de serviços quando evitar ciclo.
- `kairos/area_aluno/base.html` — adicionar a navegação do aluno (abas + Sair) e um
  bloco de sub-título/aba ativa reutilizável.
- `kairos/templates/area_aluno/inicio.html` — reduzir ao home (saudação + próxima
  sessão + atalhos); remover as listas (migram pras sub-páginas).
- `kairos/static/css/area_aluno.css` — estilos da navegação + das sub-páginas
  (reusar tokens/`components.css`; sem cores novas).
- **Testes existentes a ajustar** (`tests/test_area_aluno.py`,
  `tests/test_area_aluno_conteudo.py`): as asserções que esperavam as listas na
  `/aluno` passam a apontar para as sub-páginas novas; a saudação/atalhos seguem no
  home; o isolamento continua válido.

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): as novas rotas em `area_aluno/routes.py`
  (home + sub-páginas + foto + detalhe de acompanhamento; tudo read-only, dono na
  sessão).
- **frontend** (`frontend-writer`): a navegação no `base.html`, o home reduzido, e os
  7 templates de sub-página/detalhe (read-only, tokens da marca).
- **testes** (`teste-writer`): `tests/test_area_aluno_base.py` + ajuste dos testes
  existentes + suíte verde.

## Fora de escopo (fica pras próximas fases)
- Home rico (check-in, pulso Kairos, recado do coach) — Fases 1/2.
- Qualquer edição/registro pelo aluno (perfil editável, sinal de dor, confirmar
  presença) — válvulas das Fases 1+.
- Frente/nível, Fichas A/B, conta (idioma/tema/notif), export RGPD — fases próprias.
