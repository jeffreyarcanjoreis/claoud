# Arquitetura — Sistema Kairos

Regras fixas do projeto. Toda fatia obedece a isto; mudanças aqui são decisão explícita de arquitetura, não efeito colateral de uma issue.

## Regras fixas (valem para qualquer projeto desta metodologia)

1. **Isolamento por comportamento.** Cada comportamento do SPEC é implementado de forma independente e testável por si só. Uma issue não pode quebrar comportamentos já entregues.
2. **Thin client / fat server.** Toda regra de negócio vive no servidor. A interface exibe e coleta dados; não decide nada que o backend já não tenha decidido.

## Regras específicas do Kairos

3. **Monólito modular.** Um único serviço FastAPI, organizado em módulos por domínio (alunos, treino, dieta, ...). Nada de microserviços.
4. **Stack:** FastAPI + SQLAlchemy. Banco SQLite no MVP; a troca para PostgreSQL deve exigir só configuração, então nada de SQL específico de SQLite.
5. **Migrações versionadas desde o primeiro dia** (Alembic). Nenhuma alteração de schema fora de migração.
6. **Dados nunca inventados.** Campo sem dado é NULL no banco e "sem registro" na tela. Proibido default silencioso que pareça dado real. (Mesma regra do vault Obsidian.)
7. **Camada de IA isolada.** Quando a IA entrar (fatias futuras), toda chamada a modelo passa por um módulo próprio, para a troca de fornecedor ser barata. Fornecedor: API do Claude.
8. **Logs e tratamento de erros desde a primeira fatia.** Toda operação de escrita gera log; erro nunca é engolido silenciosamente.
9. **Backup barato desde o início.** SQLite facilita: cópia versionada do arquivo do banco antes de cada migração.
10. **Idioma:** código e identificadores em inglês; textos exibidos ao coach em português.
