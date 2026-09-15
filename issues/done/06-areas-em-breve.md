# Áreas "em breve"

## Descrição
Comportamento 8 do SPEC: as áreas ainda não construídas (Avaliação Inicial, Financeiro, Conteúdo & Comunicação) têm rota e mostram uma página "em breve" consistente, com a estrutura de cada uma esboçada.

## Depende de
02-shell-painel

## Especificação funcional
- Três novas rotas de nível de painel respondem 200, cada uma mostrando uma página "em breve" consistente, dentro do shell:
  - `GET /avaliacao-inicial` — área "Avaliação Inicial" (intake de leads).
  - `GET /financeiro` — área "Financeiro" (do negócio).
  - `GET /conteudo` — área "Conteúdo & Comunicação".
- Cada página mostra: o nome da área (h1), uma linha de contexto (eyebrow), o corpo "em breve" reutilizável (`.coming-soon`) com a frase de "por construir", e um esboço do que vai viver ali (a sub-estrutura da IA do painel, ver `07 - Direção Visual e Frontend`).
- A aba do topo correspondente fica ativa (o shell já calcula de `request.url.path`); as três continuam com o marcador "em breve" (só têm placeholder).
- Efeito colateral desejado: os links do shell para essas três áreas deixam de dar 404.
- Casos de borda: nenhum dado é inventado — as páginas são estruturais, sem números. Nenhum comportamento existente muda; os 107 testes continuam verdes.

## Pré-condições
- Issues 01-05 concluídas. Módulo `kairos/painel/` existe; `.coming-soon` existe (issue 04); o shell (issue 02) já linka e destaca essas abas.

## Arquivos a criar
- `kairos/templates/painel/area_em_breve.html` — template parametrizado de área "em breve": estende base.html; recebe `title` (nome da área), `eyebrow` (linha de contexto) e `items` (lista do que vai viver ali, cada um `{name, desc}`); renderiza eyebrow + h1 + `.coming-soon` (frase por construir) + a lista do esboço.
- `tests/test_areas_em_breve.py` — verifica: as três rotas `/avaliacao-inicial`, `/financeiro`, `/conteudo` → 200; cada uma mostra o nome da área, o corpo "em breve" e os itens do esboço; a aba de topo correta fica ativa em cada rota; e (regressão) os links do shell já não são 404.

## Arquivos a modificar
- `kairos/painel/routes.py` — adicionar as 3 rotas GET (`/avaliacao-inicial`, `/financeiro`, `/conteudo`), cada uma renderizando `painel/area_em_breve.html` com o `title`/`eyebrow`/`items` da sua área. Conteúdo dos esboços (da IA do painel):
  - Avaliação Inicial → "Respostas do Google Form da vitrine", "Ligação com Financeiro › Leads".
  - Financeiro → "Alunos ativos", "Entradas e saídas do mês", "Leads", "Cancelados", "Investimentos".
  - Conteúdo & Comunicação → "Biblioteca (3 séries, ebooks, artigos, publicações)", "Newsletter", "Comunicação com alunos (envios; futuramente WhatsApp/email)".
- `kairos/static/css/components.css` — SE necessário, um estilo mínimo para a lista de esboço dentro do `.coming-soon` (ex.: `.coming-soon .sketch`); só se o visual pedir. Nenhuma alteração ao que já existe.

## Camadas envolvidas
aplicação (rotas do painel), frontend (template area_em_breve + CSS mínimo), teste

## Status
concluída
