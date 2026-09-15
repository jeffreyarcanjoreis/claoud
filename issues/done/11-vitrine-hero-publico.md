# Vitrine — hero público (tela inicial)

## Descrição
A "tela inicial" pública do Kairos: uma página de abertura (hero) inspirada na resn.co.nz, com o logo do Kairos em 3D como protagonista (brilhante, nítido, reativo ao mouse), o slogan da marca, e um caminho para "Começar" (CTA) e "Entrar" (painel). Superfície nova, servida em `/vitrine`, sem tocar no painel (que continua em `/`) e sem autenticação (fatia futura de hospedagem).

## Decisões (com o PO)
- Escopo: **só o hero público** (sem seções do método nem login com auth real).
- Rota: **`/vitrine`**; o painel continua em `/`. O botão "Entrar" leva a `/`.
- CTA "Começar" aponta para um **Google Form** (URL a fornecer pelo PO; até lá, placeholder `#`).
- Reaproveita o Three.js local e as fontes self-hosted — sem CDN (CSP).

## Especificação funcional
- `GET /vitrine` responde 200 com uma página HTML autônoma (não usa o shell do painel: sem topbar/abas).
- A página mostra: o wordmark "Kair*o*s"; o **logo 3D** centralizado, girando sozinho (chronos) e reagindo ao mouse; o slogan **"Mover-se no *momento certo*."** e o subtítulo **"No corpo, na mente, no espírito e na comunidade."**; um CTA **"Começar"** (→ Google Form) e um link **"Entrar"** (→ `/`).
- O logo 3D é o protagonista: nítido e com presença (diferente da versão *ambiente* do painel, que é apagada/desfocada). Usa o mesmo Three.js local.
- Respeita `prefers-reduced-motion`: sem animação (logo estático), a página continua legível e utilizável.
- Se o WebGL falhar, o hero não quebra: o texto e os botões continuam funcionando (o canvas apenas não aparece).
- Sem CDN: Three.js de `/static/vendor`, fontes self-hosted via `base.css`.
- O painel em `/` e todos os 324 testes continuam intactos; nada do painel muda.
- Casos de borda: `/vitrine` é público (não exige login — não há auth ainda); o link "Entrar" é uma navegação simples para `/`.

## Pré-condições
- Three.js local já existe (`kairos/static/vendor/three.module.min.js`) e as fontes self-hosted já estão em `base.css` (feito nas fatias anteriores).
- Tokens da marca em `kairos/static/css/tokens.css`.
- **Input do PO:** a URL do Google Form do CTA (se não vier a tempo, executo com placeholder `#` e deixo um TODO visível para trocar).

## Arquivos a criar
- `kairos/vitrine/__init__.py` — pacote do comportamento "vitrine".
- `kairos/vitrine/routes.py` — `APIRouter` com `GET /vitrine` (rota fina) que renderiza `vitrine/hero.html`. Sem regra de negócio.
- `kairos/templates/vitrine/hero.html` — documento HTML autônomo (próprio `<!DOCTYPE>`, não estende `base.html`). Linka `tokens.css` + `base.css` (fontes) + `vitrine.css`. Contém o `<canvas id="vitrine-logo">`, o overlay (wordmark, slogan, subtítulo, CTA "Começar" com href do Google Form, link "Entrar" → `/`), e `<script type="module" src="/static/js/vitrine-hero.js">`.
- `kairos/static/css/vitrine.css` — layout do hero em tela cheia (fundo `--void`, overflow hidden, glow quente atrás do logo, overlay centralizado, tipografia Fraunces no slogan, estilos do CTA/Entrar/wordmark/hint "Role"). Usa os tokens da marca.
- `kairos/static/js/vitrine-hero.js` — o logo 3D em primeiro plano (versão nítida/brilhante: geometria reaproveitada — anéis toro dourado/argila, barra de equilíbrio, curva/topete em tubo, centro argila; luzes quentes; giro chronos ~0.004; reação ao mouse mais viva que a do painel). Importa `/static/vendor/three.module.min.js`. Respeita `prefers-reduced-motion` (quadro estático) e falha graciosamente sem WebGL (esconde o canvas).
- `tests/test_vitrine.py` — `GET /vitrine` → 200 e contém o slogan, o CTA "Começar" e o link "Entrar" (`href="/"`); `GET /` continua sendo o painel (o título/So conteúdo do Início permanece), garantindo que a vitrine não afetou o painel.

## Arquivos a modificar
- `kairos/main.py` — importar e registrar o `vitrine_router` (`app.include_router(vitrine_router)`), junto aos outros routers.

## Camadas envolvidas
aplicação (rota `/vitrine`), frontend (template `vitrine/hero.html` + `vitrine.css` + `vitrine-hero.js`, reaproveitando Three.js local e fontes), configuração (registro do router no `main.py`), teste.

## Fora desta fatia
- Login / autenticação real (senha/hash/sessão) — fatia de Infra/hospedagem.
- Seções do método, as 3 séries de conteúdo, scroll narrativo, cursor próprio, som — evolução do "wow".
- Mover o painel de `/` para `/painel` (decidido manter `/`).

## Status
concluída
