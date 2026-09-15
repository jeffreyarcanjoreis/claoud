---
description: Pesquisa o código existente e escreve o plano de implementação de uma issue (o como, antes do código)
---

Argumento (`$ARGUMENTS`): o nome ou número da issue em `issues/` a planejar. Se vazio, pegue a primeira issue com `Status: pendente` cujas dependências (campo "Depende de") já estejam concluídas.

Antes de escrever qualquer plano, pesquise o projeto:
- Procure código/padrões já existentes que resolvem algo parecido (grep por nomes de função, componentes ou rotas semelhantes) — o objetivo é reaproveitar, não reescrever o que já existe.
- Releia `architecture.md` e confirme em quais camadas esta issue mexe.
- Identifique as convenções de nomenclatura e estrutura de pastas já usadas no projeto para essas camadas.

Preencha a issue (`issues/NN-nome.md`) adicionando estas seções, sem tocar em código ainda:

```markdown
## Especificação funcional
<comportamento exato esperado, incluindo casos de borda>

## Pré-condições
<o que precisa já existir/estar verdadeiro antes desta issue rodar>

## Arquivos a criar
<caminho + o que cada um faz>

## Arquivos a modificar
<caminho + o que muda>

## Camadas envolvidas
<ex: modelo, rota, componente, hook, integração, teste — usado pelo /execute para escolher os subagentes>
```

Regras:
- Seja explícito sobre arquivos — esta é a seção que existe justamente para a IA não "adivinhar" na hora de executar. Nada de "atualizar os arquivos relevantes".
- Se a pesquisa revelar que a issue conflita com a regra de isolamento por comportamento (precisa tocar em pastas de outro comportamento sem motivo), pare e sinalize antes de planejar — pode ser sinal de que o `/break` dividiu errado.
- Não escreva código nesta fase, só o plano.

Ao final, mude o `Status` da issue para `planejada` e pergunte se pode seguir para `/execute`.
