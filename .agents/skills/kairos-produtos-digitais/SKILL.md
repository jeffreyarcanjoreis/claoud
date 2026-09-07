---
name: kairos-produtos-digitais
description: Use this skill whenever developing a sellable digital product for the Método Kairos — ebooks, Hotmart products, templates, mini-courses, or any file meant to be sold. Covers product ideation from existing vault content, ebook structure, sales page copy, and Hotmart-specific mechanics — all filtered through the same values filter used in the business benchmarking (no fake urgency, no manipulative bonuses, honest guarantees). Trigger whenever the user mentions "Hotmart", "e-book para vender", "infoproduto", "produto digital", or asks to package vault content into something sellable.
metadata:
  tags: hotmart, ebook, infoproduto, produto digital, vendas, kairos
---

# Kairos · Produtos Digitais e Infoprodutos (Hotmart e similares)

Empacota conhecimento já existente no vault em produtos digitais vendáveis — ebooks, mini-cursos, templates — sem trair os princípios do método no processo de venda. **Esta é a área de maior risco de contradição de valores**: o ecossistema de infoprodutos (Hotmart, Eduzz, e similares) normalmente é construído sobre táticas que o Método Kairos rejeita explicitamente.

## O filtro de valores — não negociável aqui também

Mesmo filtro já aplicado no benchmarking de negócio (ver [[11_Estudos_Desenvolvimento_Evolutivo/11-Benchmarking|11-Benchmarking]]) e na [[07_Organizacao_Negocio/07-Oferta Estruturada|Oferta Estruturada]] — reaplicado explicitamente aqui porque a cultura padrão de infoprodutos empurra exatamente na direção contrária:

- **Sem contagem regressiva falsa, sem "só até hoje à meia-noite"** — se não há um limite real (ex: um número finito de vagas de mentoria ao vivo), não fabricar um.
- **Sem prova de renda/resultado exagerada ou não verificável** ("faturei X mil em Y dias") — qualquer número usado precisa ser real e verificável, nunca aspiracional apresentado como fato.
- **Sem bônus empilhados como gatilho** ("compre agora e leve mais 5 bônus de R$997 cada") — se o produto tem valor, ele vale sozinho.
- **Garantia de processo/conteúdo, nunca de resultado de vida** ("garanta seu corpo dos sonhos em 30 dias") — mesma lógica já fixada na Oferta Estruturada: o que se garante é a qualidade e completude do material, não uma transformação corporal fixa (isso contradiz Impermanência).
- **Sem gatilho de escassez de vagas fabricado** para produto digital — um ebook não tem "vagas limitadas" de verdade; dizer isso é mentira, ponto.
- **Depoimentos, se usados, precisam ser reais e verificáveis** — nunca fabricados ou de "clientes fictícios ilustrativos".

Se em algum momento a estrutura padrão de venda de infoproduto pedir um desses elementos, a resposta é a mesma da Oferta Estruturada: declarar explicitamente que o produto não usa esse mecanismo, em vez de forçar uma versão manipuladora "suavizada".

## 1. Ideação — o que do vault já pode virar produto

Antes de criar do zero, mapear o que já existe e só precisa ser empacotado:

| Conteúdo já existente | Produto possível |
|---|---|
| [[03_Metodologia/Os Quatro Treinos/Os Quatro Treinos — Explicação Detalhada\|Os Quatro Treinos — Explicação Detalhada]] | Ebook curto, pilar central do catálogo digital |
| [[02_Ideologia_Valores/Ideologia e os Cinco Princípios\|Ideologia e os Cinco Princípios]] | Ebook filosófico/manifesto, produto de entrada de baixo custo |
| [[05_Treinos_Protocolos/Sistema de Prescrição — Avaliação, Níveis e Periodização\|Sistema de Prescrição]] (quando Fichas A-F chegarem) | Template/planilha de autoavaliação |
| [[07_Organizacao_Negocio/07-Produto de Entrada\|Mini-diagnóstico "Qual é o seu momento agora?"]] | Versão digital vendável expandida (não a versão gratuita de captação) |
| Futuro Manual de Formação (lacuna conhecida) | Mini-curso para outros professores — só depois da validação (ver [[Modelo de Negócio e Organização]], Parte 3) |

**Regra:** nenhum produto digital de formação/certificação deve ser lançado antes da metodologia estar validada com alunos reais — mesma sequência já fixada no plano de negócio. Ebooks de conteúdo/filosofia não têm essa restrição.

## 2. Estrutura de ebook

1. **Capa e título** — usar `kairos-voz-humana` e o Guia de Voz para o título soar como convite, não como clickbait ("O Guia Definitivo Que Vai Mudar Sua Vida" é exatamente o tom errado).
2. **Introdução** — nomear o estado real do leitor antes de apresentar a solução (mesma fórmula Estado → Ruptura do [[09_Divulgacao_Conteudo/09-Guia de Voz e Copywriting|Guia de Voz]]).
3. **Capítulos** — do simples ao complexo (fundamento pedagógico do método, ver pasta 03) — nunca despejar tudo de uma vez.
4. **Fechamento** — convite direto para o próximo passo (outro produto, a Avaliação Inicial, ou simplesmente aplicar o que foi lido) — nunca um cliffhanger manipulador que deixa o conteúdo incompleto de propósito.
5. **Geração do arquivo real:** usar a skill nativa de PDF ou Word (ver [[09_Divulgacao_Conteudo/09-Ferramentas para Slides e Ebook|Ferramentas para Slides e Ebook]]) para produzir o arquivo final — não inventar conteúdo de capítulos sem grounding no que já existe no vault.

## 3. Página de vendas (sales page) — diferente da copy de rede social

**Importante:** a página de vendas de um produto Hotmart tem um trabalho diferente do post de Instagram (`kairos-reels`) — ali a pessoa já está considerando comprar, então a página precisa resolver objeções e mostrar o conteúdo real, não gerar descoberta. Estrutura honesta:

1. **Título** — o resultado do processo (não do corpo/vida), específico.
2. **Para quem é** — nomear os avatares reais (ver [[07_Organizacao_Negocio/07-Avatares e Entrevistas de Descoberta|Avatares]]), não "para todo mundo que quer emagrecer".
3. **O que está incluído** — lista real e completa do conteúdo, sem inflar número de páginas/aulas como métrica de valor.
4. **Prova** — só o que for real (link para conteúdo público, credenciais reais de Jeffrey, ver Seção 1 do [[07_Organizacao_Negocio/07-Registro de Due Diligence para Investidores|Registro de Due Diligence]]) — nunca depoimento fabricado.
5. **Preço e garantia** — garantia de processo/reembolso claro, sem letra miúda escondendo a real cobertura.
6. **CTA único** — comprar. Não empilhar múltiplos CTAs concorrentes.

## 4. Mecânica específica do Hotmart

- **Formatos comuns:** ebook (PDF), mini-curso em vídeo (usar o pipeline Seedance+Remotion para as aulas, ver [[09_Divulgacao_Conteudo/09-Pipeline de Producao de Video (Seedance + Remotion)|Pipeline de Produção de Vídeo]]), templates/planilhas (Excel/Google Sheets).
- **Precificação:** coerente com "vender transformação, não horas" (ver [[Modelo de Negócio e Organização]]) — um ebook de conteúdo tende a ficar na faixa de produto de entrada (baixo custo), não no mesmo patamar do 1-a-1.
- **Programa de afiliados (se usado no futuro):** manter a mesma exigência de honestidade — nenhum afiliado deveria ser instruído a usar táticas que o próprio Jeffrey não usaria.
- **Checkout:** Hotmart já cuida da parte técnica de pagamento — o trabalho real desta skill é o conteúdo e a página de vendas, não a configuração da plataforma.

## Checklist antes de publicar qualquer produto digital
- [ ] O conteúdo é real e completo, não um teaser manipulador?
- [ ] Nenhuma escassez ou urgência fabricada?
- [ ] A garantia é de processo/conteúdo, não de resultado de vida?
- [ ] Prova/depoimentos são reais e verificáveis, ou simplesmente não existem ainda (o que é honesto dizer)?
- [ ] Passou pelo checklist da `kairos-voz-humana` (soa humano, não genérico de infoproduto)?
- [ ] Um só CTA na página de vendas?

## Status
Skill criada em 2026-07-07, a pedido de Jeffrey. Nenhum produto digital foi criado ainda — esta skill fica pronta para quando o primeiro ebook/produto for de fato desenvolvido.
