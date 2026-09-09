# Extensão da vitrine — landing (método + convite)

## Descrição
Estender a vitrine (que era só o hero) para uma landing que rola, com seções abaixo do hero. Copy ancorada na volt (skill kairos-method para a voz). Só frontend.

## Decisões (com o PO)
- Escopo: hero (já feito) + **Seção "O método"** + **Seção de convite (CTA)**. As seções "5 princípios" e "3 séries" foram **removidas** desta fatia (ficam para depois).
- Copy: puxada da volt (`08_Identidade_Marca/Metodo Kairos — Texto-base`), aprovada pelo PO antes de codar.
- CTA "Começar" com placeholder `href="#"` (falta a URL do Google Form).

## Especificação funcional
- `GET /vitrine` continua 200 e agora, abaixo do hero, mostra a seção "O método" (eyebrow "O método", "Cada corpo é único.", "o método se adapta a você", "uma pessoa melhor") e a seção de convite ("...começa agora." + botão `.v-cta-botao` "Começar").
- A página rola: o hero é a primeira tela (100vh) com o logo 3D; o canvas fica fixo atrás e as seções opacas passam por cima.
- Revelação suave das seções ao entrar na viewport (IntersectionObserver), como progressive enhancement: classe `.js` no `<html>` (sem JS, seções visíveis); respeita `prefers-reduced-motion`; independe do WebGL.
- Não contém as seções removidas (nada de "princípios", "Infância em Movimento", "A Arte do Treinamento").
- Painel (`/`) e rotas intactos.

## Arquivos modificados
- `kairos/templates/vitrine/hero.html` — hero vira `<section class="hero">`; abaixo, `<section class="v-metodo reveal">` e `<section class="v-cta reveal">`.
- `kairos/static/css/vitrine.css` — libera scroll (canvas fixo `pointer-events:none`; seções opacas), tipografia das seções, botão CTA grande, e a revelação `.js .reveal`/`.in-view`.
- `kairos/static/js/vitrine-hero.js` — marca `.js` no `<html>` e adiciona `setupReveals()` (IntersectionObserver), além do logo 3D já existente.
- `tests/test_vitrine.py` — +2 testes (seções método/CTA presentes; princípios/séries ausentes).

## Camadas envolvidas
frontend (template + css + js), teste.

## Validação
330 testes verdes. Navegador: hero como primeira tela; rolar revela "O método" e o convite (in-view, opacidade 1); sem erros no console; `.js` ativo; CTA "Começar" (href="#").

## Status
concluída
