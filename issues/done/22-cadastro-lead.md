# Issue 22 — Cadastro público (Avaliação Inicial nativa) → cria a lead

## Status
concluída

## Contexto / decisão do PO
O "Começar" deixa de ser um link pro Google Form e vira um **cadastro nativo** no
app, com as perguntas do `Template - Perfil do Aluno`. Cada cadastro enviado **cria
uma lead** (um `Contato`) que o coach revê no Início. Decisões do PO:
- **O cadastro nativo SUBSTITUI o Google Form** como porta de entrada (some a
  dependência do link do Form e a central que linkava pro Google).
- **Guardar os dados de saúde no app, COM consentimento** — caixa de consentimento
  obrigatória + nota curta de privacidade. (Endurecimento RGPD real — criptografia,
  controle de acesso — vem com a hospedagem; hoje é SQLite local.)

## Reversão explícita registrada
A issue 20 tinha decidido "sem dados de saúde no app". O PO reverteu: agora o app
**guarda** saúde, com consentimento. Atualizar o docstring de
`kairos/contatos/models.py` (tira a nota "sem saúde"; passa a explicar que guarda
saúde mediante consentimento, e que o endurecimento RGPD vem com a hospedagem).

## Perguntas do cadastro (o que a pessoa responde)
Baseado no template (blocos Dados Gerais + Objetivos + Histórico de Saúde). Campos
respondidos pela pessoa (coach-side como início/modalidade/fase ficam de fora):
- **Nome*** (obrigatório)
- **Idade** (número, opcional)
- **Sexo** (select opcional: Masculino / Feminino / Outro / Prefiro não informar)
- **Contato*** (telefone/WhatsApp/e-mail — obrigatório pra dar retorno)
- **Objetivo principal** (texto)
- **Objetivos secundários** (texto)
- **Prazo desejado** (texto curto)
- **Frequência semanal desejada** (opcional: 1-2 / 3-4 / 5+)
- **Condições / Patologias** (texto — saúde)
- **Lesões ou Restrições** (texto — saúde)
- **Medicamentos em uso** (texto — saúde)
- **Nível de condicionamento** (select: Sedentário / Iniciante / Intermediário / Avançado)
- **Consentimento*** (checkbox OBRIGATÓRIO: "Autorizo o uso dos meus dados,
  inclusive de saúde, para o desenho do meu treino.")

## Modelo de dados
Expandir o `Contato` existente (migração **0016**, head atual 0015 → 0016). Todos os
campos novos **nullable** (o cadastro público preenche; o quick-add manual do Início
deixa NULL). Adicionar:
`idade`(Int), `sexo`(String), `objetivo`(Text), `objetivos_secundarios`(Text),
`prazo_desejado`(String), `frequencia_desejada`(String), `condicoes`(Text),
`lesoes`(Text), `medicamentos`(Text), `nivel_condicionamento`(String),
`consentimento`(Boolean, default False), `origem`(String — "cadastro" | "manual").
Mantém: nome, contato, status, observacao, created_at.

## Serviço `kairos/contatos/service.py`
- `NIVEIS_CONDICIONAMENTO`, `SEXO_OPCOES`, `FREQUENCIA_OPCOES` (constantes + rótulos).
- `create_cadastro(**campos)` — cria uma lead a partir do cadastro público: valida
  nome e contato obrigatórios e **consentimento obrigatório = True** (senão
  `ValidationError`); normaliza idade (int válido/opcional); status nasce
  `a_contatar`; `origem="cadastro"`; guarda todos os campos.
- `create_contato(...)` (o quick-add manual) — mantém, agora setando `origem="manual"`.
- `get_contato_detail(id)` — devolve TODOS os campos + rótulos pt-BR (nível, sexo,
  frequência, status) pra tela de detalhe.
- `list_contatos_abertos()` — inalterado (nome + status na lista).

## Rotas
- **Público** (página autônoma, sem shell do painel — como a vitrine):
  - `GET /comecar` — renderiza o formulário de cadastro (`contatos/cadastro.html`).
  - `POST /comecar` — cria a lead via `create_cadastro`; em erro re-renderiza com a
    mensagem e os valores; em sucesso mostra um estado de agradecimento ("Recebido!
    Em breve entro em contato."). Nada de dado sensível na URL (POST form).
- **Painel** (coach):
  - `GET /contatos/{id}` — página de detalhe da lead (estende o layout do painel):
    mostra o perfil enviado (dados gerais, objetivos, saúde, consentimento, origem,
    data). Botão voltar pro Início.
  - Na lista do Início, cada card ganha um link "ver" → `/contatos/{id}`.
- Rotas existentes `/contatos[/{id}/status|/remover]` mantidas.

## Início (`painel/inicio.html` + `inicio_context`)
- A **central** da seção Novos contatos deixa de apontar pro Google. Vira
  "Compartilhe o cadastro" com o link interno `/comecar` (o coach envia pra quem tem
  interesse). Remover os botões "Abrir respostas (Google)"/"Compartilhar o Form" e o
  uso de `avaliacao_form_url`/`avaliacao_respostas_url` no Início.
- Manter o quick-add manual + a lista; cada item com "ver" (detalhe) além de
  status/remover.

## Vitrine (`vitrine/hero.html` + `vitrine/routes.py`)
- O CTA "Começar" (topo) e o botão da seção "Vamos começar" passam a apontar pra
  **`/comecar`** (link interno, sempre ativo). Remover o condicional "Em breve"/
  `avaliacao_form_url` — não depende mais do Google. A rota da vitrine volta a não
  precisar do `avaliacao_form_url`.

## Config
- As funções `avaliacao_form_url()`/`avaliacao_respostas_url()` ficam órfãs. Deixar
  no `config.py` por ora (inofensivas) OU removê-las — decidir no /execute; se
  remover, ajustar os testes que as citam. (Proposta: **remover**, já que a decisão
  é substituir o Google.)

## Frontend / CSS
- `contatos/cadastro.html` — página pública standalone (reusa tokens/base; visual
  coerente com a vitrine: fundo escuro da marca, sem o shell). Formulário em blocos
  (Dados gerais / Objetivos / Saúde) + consentimento + nota de privacidade + botão
  "Enviar cadastro". Estado de sucesso.
- Estilos do formulário público e da página de detalhe da lead (reusar componentes;
  sem cores novas). `inputmode`/`type` adequados (idade numérica; textos longos em
  textarea).

## Testes
- `test_contato_model`: atualizar — agora o `contatos` TEM as colunas novas
  (inclusive saúde) + consentimento/origem; migração 0016 vira head. Ajustar a
  asserção antiga que exigia "sem coluna de saúde".
- Serviço: `create_cadastro` (nome/contato/consentimento obrigatórios; consentimento
  False → erro; campos guardados; origem "cadastro"); `create_contato` origem
  "manual"; `get_contato_detail` traz tudo com rótulos.
- Público: `GET /comecar` 200 e mostra os campos + consentimento; `POST /comecar`
  válido cria a lead e mostra sucesso; sem consentimento → erro; sem nome/contato →
  erro.
- Painel: `GET /contatos/{id}` mostra o perfil; "ver" aparece na lista.
- Início: central mostra o link do cadastro `/comecar` (não mais Google).
- Vitrine: CTA aponta pra `/comecar` (não "Em breve").
- Ajustar testes obsoletos (vitrine "Em breve"; contatos central Google; head-ref
  dos test_*_model pra 0016; test_scaffold rollback pra 0015 + drop das novas
  colunas se aplicável — na verdade 0016 é ALTER, então o scaffold só precisa do
  head 0016).
- Rodar a suíte inteira; reportar total verde.

## FUTURO (fora de escopo desta fatia)
- **Lead → Aluno**: um botão "criar aluno a partir desta lead" que semeia o Perfil
  do Aluno já preenchido (nome, idade, sexo, contato, objetivo, saúde). Natural
  continuação — fica pra próxima fatia.
- Anti-spam/captcha e endurecimento RGPD: com a hospedagem.

## Camadas / subagentes
banco-migracao-writer (0016 + model) → servico-writer (create_cadastro,
get_contato_detail, constantes) → aplicacao-writer (rotas /comecar público + detalhe
+ Início central + vitrine CTA + config) → frontend-writer (cadastro.html público,
detalhe da lead, CSS) → teste-writer (suíte).
