---
description: Implementa uma issue já planejada, com testes, usando subagentes especializados por camada
---

Argumento (`$ARGUMENTS`): o nome ou número da issue a executar. Se vazio, pegue a primeira issue com `Status: planejada`. Se a issue não tiver sido planejada ainda (sem seção "Especificação funcional"), pare e peça para rodar `/plan` nela primeiro.

Para cada camada listada em "Camadas envolvidas":
1. Verifique se já existe um subagente para essa camada em `.claude/agents/<camada>-writer.md`.
2. Se não existir, crie-o agora: escopo estreito (só aquela camada), instruções específicas do stack do projeto, e referência às skills relevantes já disponíveis no projeto para aquela camada.
3. Delegue a implementação daquela parte da issue ao subagente correspondente, passando a seção relevante do plano (não a issue inteira) como contexto.

Depois que todas as camadas estiverem implementadas:
- Escreva/atualize os testes que cobrem a especificação funcional da issue.
- Rode os testes e confirme que passam.
- Confirme contra `architecture.md` que a implementação não violou isolamento por comportamento nem a regra thin client/fat server (nenhum segredo ou lógica de negócio vazou pro frontend).

Ao final, mude o `Status` da issue para `concluída`, mova o arquivo para `issues/done/`, e diga qual é a próxima issue pendente (ou planejada) na fila.
