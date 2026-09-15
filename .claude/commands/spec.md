---
description: Escreve ou atualiza o SPEC.md do projeto (o quê construir, antes de qualquer código)
---

Escreva ou atualize `SPEC.md` na raiz do projeto. Se `$ARGUMENTS` descrever o projeto/feature, use isso como base; caso contrário, pergunte ao usuário o essencial antes de escrever.

Estrutura do SPEC.md (adapte os nomes de seção ao tipo de projeto — ex. um CLI usa "Comandos" em vez de "Página"):

1. **Overview** — o que o projeto/feature faz e para quem, em 3-5 frases. Sem enrolação de marketing.
2. **Áreas/Páginas/Comandos** — as superfícies principais que o usuário final toca (páginas de um app, comandos de um CLI, endpoints de uma API).
3. **Componentes** — as peças reutilizáveis que essas áreas vão precisar.
4. **Comportamentos** — o que o sistema faz em resposta a ações específicas do usuário, um comportamento por item, frase curta e verificável (ex.: "Quando o usuário submete um prompt vazio, o botão de enviar fica desabilitado").

Regras:
- Cada comportamento deve ser pequeno o bastante para virar uma issue única depois (`/break`). Se um comportamento tem "e" no meio misturando duas coisas, quebre em dois.
- Não descreva *como* implementar (arquivos, bibliotecas, algoritmos) — isso é trabalho do `/plan`, não do `/spec`.
- Se `architecture.md` ainda não existir no projeto, crie-o agora com as duas regras fixas da skill `workflow` (isolamento por comportamento; thin client/fat server) mais qualquer regra adicional específica deste projeto que o usuário mencionar.
- Se já existir um SPEC.md, trate esta chamada como uma atualização incremental — mostre um resumo do que mudou, não reescreva do zero.

Ao final, mostre o SPEC.md e pergunte se pode seguir para `/break`.
