---
name: "source-command-break"
description: "Quebra o SPEC.md em issues pequenas e acionáveis (issues/*.md)"
---

# source-command-break

Use this skill when the user asks to run the migrated source command `break`.

## Command Template

Leia `SPEC.md`. Se não existir, pare e diga ao usuário para rodar `/spec` primeiro.

Quebre cada comportamento (ou grupo mínimo de comportamentos que precisam nascer juntos) em uma issue própria dentro de `issues/`. Nomeie os arquivos `issues/NN-nome-curto.md` (NN = ordem de execução sugerida, considerando dependências: dados antes de UI, autenticação antes de rotas protegidas, etc).

Cada arquivo de issue começa só com isto (o `/plan` preenche o resto depois):

```markdown
# <título curto da issue>

## Descrição
<o comportamento do SPEC.md que esta issue implementa, 1-3 frases>

## Depende de
<outras issues que precisam estar prontas antes, ou "nenhuma">

## Status
pendente
```

Regras:
- Uma issue = uma unidade que dá para implementar e testar isoladamente. Se ao escrever a descrição você usar "e" ligando duas ações independentes, é sinal de que deveria ser duas issues.
- Respeite a regra de isolamento por comportamento do `architecture.md`: se duas issues vão precisar editar o mesmo arquivo por razões não relacionadas, repense a divisão.
- Não invente comportamento que não está no SPEC.md — se faltar algo, aponte a lacuna e sugira voltar para `/spec` em vez de preencher por conta própria.

Ao final, liste as issues criadas em ordem e pergunte se pode seguir para `/plan` na primeira.
