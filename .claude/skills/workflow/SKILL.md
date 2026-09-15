---
name: workflow
description: Use whenever starting a new software project or a substantial new feature — before writing any code. Replaces vibe coding with a Spec → Break → Plan → Execute loop (spec-driven development), the same pattern formalized in 2026 by GitHub Spec Kit, OpenSpec, AWS Kiro and Claude Code Skills. Trigger on "novo projeto", "vamos construir/criar um app/sistema/feature", "bora começar um projeto do zero", or any request to build something non-trivial with AI.
metadata:
  tags: spec-driven-development, workflow, anti-vibe-coding, architecture, subagents
---

# Workflow — Anti-Vibe Coding (Spec-Driven Development)

Vibe coding (pedir feature em prosa solta e deixar a IA decidir tudo) quebra assim que o projeto sai do protótipo: código bagunçado, a IA ignora o que foi pedido, uma mudança quebra outra parte, e aparecem falhas de segurança. Este workflow substitui isso por um loop de 4 fases, cada uma com seu comando: **`/spec` → `/break` → `/plan` → `/execute`**.

Validado contra a prática de mercado de 2026 (GitHub Spec Kit, OpenSpec, AWS Kiro, Claude Code Skills) — não é uma convenção inventada, é o padrão que a indústria convergiu para resolver exatamente estes 4 problemas.

## Os 4 problemas que este workflow resolve

| Problema do vibe coding | Causa raiz | Como este workflow resolve |
|---|---|---|
| IA "engasga" em tarefas grandes | Contexto lotado com um projeto inteiro de uma vez | `/spec` + `/break` — quebra tudo em issues pequenas e isoladas |
| Código bagunçado / duplicado | IA não pesquisa o que já existe antes de escrever | `/plan` — pesquisa padrões e imports existentes antes de implementar |
| IA "não obedece" | Pedido diz o quê fazer, não diz quais arquivos tocar | `/plan` — a issue passa a listar exatamente os arquivos a criar/modificar |
| Arruma uma coisa, quebra outra | Responsabilidades misturadas na mesma pasta/arquivo | Regra de isolamento por comportamento (ver abaixo) + `architecture.md` |
| Gafes de segurança | Lógica de negócio e segredos vazam pro frontend | Regra thin client / fat server (ver abaixo) + `architecture.md` |

## As duas regras de arquitetura, sempre válidas

Todo projeto criado com este workflow mantém um `architecture.md` na raiz com (no mínimo) estas duas regras — `/plan` e `/execute` sempre consultam esse arquivo antes de tocar em código:

1. **Isolamento por comportamento**: cada funcionalidade/behavior vive na sua própria pasta/módulo. Editar um comportamento não deve exigir tocar em arquivos de outro. Se uma issue pede mudança em dois comportamentos ao mesmo tempo, é sinal de que a spec/issue está mal quebrada — volte para `/break`.
2. **Thin client, fat server**: o frontend nunca contém lógica de negócio, nunca guarda chaves/segredos, e só captura intenção do usuário e reage a resultados que vêm do backend. Qualquer decisão de negócio, validação de permissão ou dado sensível vive no servidor.

## O loop

```
/spec     → escreve/atualiza SPEC.md (o quê construir)
/break    → quebra o SPEC.md em issues/*.md pequenas e acionáveis
/plan     → escolhe uma issue, pesquisa o código existente, escreve o plano de implementação nela (o como)
/execute  → implementa a issue já planejada, com testes, usando subagentes especializados por camada
```

Cada fase só começa depois da anterior estar escrita em arquivo — nunca pule direto para código sem uma issue planejada. Repita `/plan` → `/execute` para cada issue até o SPEC.md estar todo implementado.

## Subagentes especializados por camada

Na fase `/execute`, não use um único agente genérico para tudo. Identifique as camadas que a issue toca (ex.: modelo/dados, rota/endpoint, componente de UI, hook, integração externa, testes) e use ou crie em `.claude/agents/` um subagente por camada, no padrão `<camada>-writer.md`, cada um com escopo estreito e as skills relevantes daquela camada. Isso mantém cada agente com contexto pequeno e focado, e reforça o isolamento por comportamento.

Se o projeto ainda não tem esses subagentes, crie-os na primeira execução com base nas camadas reais do stack do projeto (não copie camadas de outro projeto se não fizerem sentido ali).

## Onde as coisas vivem no projeto

- `SPEC.md` — na raiz, produzido/atualizado por `/spec`.
- `architecture.md` — na raiz, regras de arquitetura e segurança do projeto.
- `issues/*.md` — uma issue por arquivo, criadas por `/break`, preenchidas com o plano por `/plan`, riscadas/movidas para `issues/done/` por `/execute`.
- `.claude/agents/*-writer.md` — subagentes por camada, criados sob demanda.

## Quando não usar este workflow

Para scripts descartáveis, protótipos de exploração de uma sessão só, ou mudanças triviais (typo, ajuste de estilo, bump de versão), o overhead de spec → break → plan é desperdício — trate como o que é: rápido e direto. Este workflow é para o momento em que o projeto vai virar algo real e precisa sobreviver a mais de uma sessão.
