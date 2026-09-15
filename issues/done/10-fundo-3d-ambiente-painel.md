# Logo 3D como fundo ambiente do painel

## Descrição
Trazer o logo do Kairos em 3D para o fundo do painel inteiro (shell), na versão ambiente do doc 07: apagado, desfocado, lento, atrás do conteúdo legível, pausável. Sem tocar em dados/rotas/banco — camada visual do shell.

## Decisões (com o PO)
- Escopo: **shell inteiro** (todas as telas do painel), não só o Início.
- Three.js **empacotado localmente** (sem CDN, coerente com a CSP).
- Escolhido em vez de construir a vitrine-hero real agora (que puxaria login/auth/hospedagem).

## Especificação funcional
- Canvas fixo atrás de tudo com o logo 3D (anéis toro, barra, curva/topete, centro), giro lento + leve reação ao mouse.
- Ambiente: opacidade ~0.24 + blur 2px (CSS); scrim escuro sutil protege a leitura; conteúdo em z-index acima.
- Botão "pausar fundo" (localStorage lembra o estado); pausa sozinho com a aba oculta; respeita prefers-reduced-motion (estático); se WebGL falhar, esconde sem quebrar o app.

## Arquivos
- Criados: `kairos/static/vendor/three.module.min.js` (Three.js v160 local), `kairos/static/js/painel-fundo.js`.
- Modificados: `kairos/templates/base.html` (canvas + scrim + botão + script module), `kairos/static/css/shell.css` (fundo/scrim/botão + z-index do conteúdo).

## Validação
324 testes verdes (mudança no base.html é aditiva). Navegador: WebGL ativo e init completo (`__kairosFundoReady`), sem erros no console, Three.js servido de /static/vendor, botão pausar/retomar funciona e persiste, conteúdo legível (z-index 1 sobre canvas z-index 0), shell intacto. Screenshot não disponível no ambiente (painel não compõe frames) — comprovado por DOM/estado.

## Status
concluída
