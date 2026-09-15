# Issue 21 — Vitrine: abas Método, Profissionais e Vamos começar

## Status
concluída

## Contexto / decisão do PO
Expandir a vitrine pública (`/vitrine`) com três abas: **Método**, **Profissionais**
e **Vamos começar**. Hoje a vitrine é uma landing única que rola: hero (logo 3D em
tela cheia) + seções `.v-secao` que passam por cima do canvas fixo, com âncoras de
scroll suave e revelação no scroll.

## Interpretação de "abas" (confirmar na aprovação)
As três abas viram **três seções** da mesma landing, alcançadas pelo **menu do
topo** que rola suavemente até elas (âncoras `#metodo`, `#profissionais`,
`#vamos-comecar`) — preservando o design atual (logo 3D atrás, seções com véu,
reveal no scroll), sem virar um SPA de troca de aba por JS.
> Alternativa, se você preferir: abas de verdade que trocam o conteúdo mostrando
> uma por vez (esconde as outras). É mais interação em JS e foge do scroll-reveal
> atual. **Recomendo a versão scroll-âncora** por coerência com o que já existe.

## Estrutura da página (mesma `vitrine/hero.html`)
1. **Hero** (mantém). O menu do topo passa a ter: `Método` · `Profissionais` ·
   botão CTA `Começar` · `Entrar`. Os dois primeiros rolam para as seções; o CTA
   rola para (ou aponta para) "Vamos começar".
2. **#metodo — "O Método"** (expande a seção atual "O método").
3. **#profissionais — "Profissionais"** (nova).
4. **#vamos-comecar — "Vamos começar"** (evolui a seção `.v-cta` atual): só o
   gatilho para o formulário da Avaliação Inicial.

## Aba MÉTODO (conteúdo)
Adaptar a "Apresentação do Método para Alunos" que o PO passou — **em pt-BR, voz
Kairos, SEM jargão interno do vault, sem wikilinks, sem seção "Fontes/Status"**.
Usar as skills `kairos-method` (fidelidade ao método) e `kairos-voz-humana` (soar
humano) na redação. Substância (mantida fiel ao texto do PO):
- Abertura forte: **"Não existe o treino certo. Existe o movimento certo para
  você, agora."** + o parágrafo do caminho inverso (parte de quem você é, não de
  um protocolo pronto).
- **A jornada, passo a passo** (5 blocos, como cards/lista):
  1. Avaliação Inicial (três camadas: fatos · estado atual · intenção).
  2. Cada sessão tem estrutura viva (5 momentos).
  3. Quatro dimensões (Físico · Mental · Espiritual · Social).
  4. Progressão por domínio real (Fundação → Construção → Domínio → Maestria),
     não por calendário.
  5. Acompanhamento além de carga/repetição (presença · autorregulação · autonomia).
- **O que você vai conquistar** (disciplina construída, autoconfiança real,
  resiliência, atenção/presença, domínio do movimento).
- **Como eu vou te ajudar** (ler o seu momento a cada sessão, presença real).
- **Como isso é feito, na prática** (Avaliação Inicial → definição do formato →
  ciclo de acompanhamento → conversa de fechamento de ciclo).
Layout: reusar `.v-titulo/.v-eyebrow/.v-texto/.v-destaque`; para as listas de
5 passos / 4 dimensões / conquistas, criar cards discretos reaproveitando os
tokens (sem cores novas). É uma seção longa — quebrar em sub-blocos legíveis.

## Aba PROFISSIONAIS (conteúdo)
Apresentar os profissionais. **Hoje só há um: Jeffrey Reis.** Um card de
profissional com: nome, papel (criador do Método Kairos · personal trainer) e uma
descrição curta. **Regra 6 — não inventar credenciais:** vou redigir um texto
honesto a partir do que o método já diz sobre a filosofia do trabalho; **o PO
confirma/edita nome exato, título e bio na aprovação**, e pode me passar uma
**foto** (opcional; sem foto, uso um monograma "K"/inicial tasteful como
placeholder). Estrutura preparada para receber mais profissionais no futuro
(grid de cards), mas começa com um.

## Aba VAMOS COMEÇAR (conteúdo)
Só o **gatilho para o formulário da Avaliação Inicial**. Um título curto + uma
frase + o botão `Começar` que aponta para o Google Form.
- A rota passa `avaliacao_form_url` (de `config.avaliacao_form_url()`).
- **Quando configurado:** o botão (e o CTA do topo) apontam para o link do Form,
  `target="_blank" rel="noopener"`.
- **Quando NÃO configurado (estado atual):** como é página pública, nada de
  "configure aqui". O botão degrada com elegância — fica como "Em breve" (ou
  rola só para a seção) — sem link quebrado. Ativa sozinho quando o PO fornecer
  o link público de resposta do Form (`.../viewform`).
- Remove os dois `<!-- TODO: trocar href pela URL do Google Form -->` /
  `href="#"` atuais (nav e seção), substituídos pelo link real/estado gracioso.

## Camadas / arquivos
- **aplicacao-writer**: `kairos/vitrine/routes.py` passa a montar o contexto com
  `avaliacao_form_url` (import de `kairos.config`). Continua rota fina.
- **frontend-writer**: `kairos/templates/vitrine/hero.html` (nav + três seções +
  conteúdo) e `kairos/static/css/vitrine.css` (estilos das novas seções/cards,
  âncoras, grid de profissionais, botão em estado "em breve"). Reusar tokens;
  sem framework JS novo (o `vitrine-hero.js` de reveal/scroll já cobre). Garantir
  `scroll-margin-top` nas seções para as âncoras não ficarem escondidas.
- **teste-writer**: estender/!criar teste da vitrine — `GET /vitrine` 200 e
  contém as três seções (`id="metodo"`, `id="profissionais"`, `id="vamos-comecar"`),
  o nome "Jeffrey Reis", a frase de abertura do método, e o menu com os links de
  âncora; CTA aponta para o Form quando a env está setada e degrada quando não.

## Fora de escopo
- Login/auth (segue fatia futura de hospedagem).
- Foto real do profissional se o PO não fornecer agora (placeholder).
- Seções "5 princípios" e "3 séries" (ainda adiadas).
