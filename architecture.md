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

## Princípios do método na interface (valem para toda tela do aluno e do coach)

11. **O nível é autodeterminado pelo aluno.** "Nível" (Fundação / Construção / Domínio / Maestria) e todo progresso no método são **reconhecidos pela própria pessoa**: ela se julga capaz ou não, realiza com maestria ou com dificuldade, identifica suas habilidades e reconhece suas necessidades — e pode rever quando sentir. A interface **nunca** dá nota, ranking ou nível concedido de cima; não há barra de progresso a "ganhar". A escolha de esforço/variação (base, regressão, progressão) é da pessoa, lendo o próprio corpo — não uma regra imposta.
12. **O verbo é da pessoa.** Toda escrita voltada ao aluno usa a primeira pessoa do autoconhecimento — *eu reconheço, eu escolho, eu percebo* — e honra a autorregulação e a autonomia (criar autonomia, não dependência).
13. **O papel do coach na interface é conscientizar, acolhe, respeitar, educar.** O coach aparece como espelho e presença que acompanha — nunca como régua que classifica, corrige de cima ou tutela. Mesmo a passagem de nível é reconhecida pela pessoa; o coach conscientiza, não concede.
14. **O momento certo (kairos).** O que o aluno registra de si (check-in, sensação, limite do dia) é a pessoa se lendo; o sistema e o coach **respeitam e ajustam** a essa leitura — o limite de hoje é dela. "Mover-se no momento certo."
