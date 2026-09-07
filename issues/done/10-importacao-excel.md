# Importação de aluno via Excel

## Descrição
Comportamento 11 do SPEC: comando de importação que recebe a pasta de um aluno em Excel, cria o aluno com os campos reconhecidos (nome, idade, período, objetivo) e lista o que não conseguiu importar. É o comportamento que valida a fatia com o caso real (Marcos Anastasio).

## Depende de
02-cadastro-aluno

## Especificação funcional

Comando: `python -m kairos.cli importar-aluno "<pasta do aluno>" [--simular]`

- Lê TODOS os `.xlsx` da pasta indicada, em modo somente leitura — os arquivos originais nunca são modificados.
- Localiza o cabeçalho procurando, na primeira coluna de cada planilha, rótulos `atleta`, `idade`, `periodo`, `objetivo` (comparação sem acentos, sem maiúsculas e ignorando espaços extras), e lê o valor na coluna ao lado. Os rótulos NÃO estão em linhas fixas: no arquivo de treino começam na linha 2, no de dieta na linha 1 — por isso a busca é por rótulo, nunca por número de linha.
- Campos reconhecidos e o que fazem:
  - `atleta` → nome do aluno. Espaços internos repetidos são colapsados ("Marcos  anastasio" → "Marcos anastasio"). O texto NÃO é recapitalizado nem corrigido — o coach edita depois na tela se quiser.
  - `objetivo` → objetivo, importado como está escrito (ex.: "definiçao e hipertrofia", sem correção ortográfica).
  - `periodo` → extrai as datas no formato DD/MM/AAAA por expressão regular, tolerando o lixo entre elas ("inicio :02/01/2024 �termino 15/02/2024"). A primeira data vira início do plano, a segunda término. Se só houver uma data, ela vira o início e o término fica vazio.
  - `idade` → **NÃO é importado** e entra no relatório de não importados, com o motivo: o sistema guarda data de nascimento, e derivar uma data a partir de "29 anos" seria inventar dado (regra 6 do architecture.md).
- Quando a mesma etiqueta aparece nos dois arquivos com valores diferentes, vale o primeiro encontrado (ordem alfabética dos arquivos) e a divergência é relatada como aviso.
- Ao final imprime, em português: os campos que serão gravados, o id criado, e a lista do que NÃO foi importado com o motivo de cada item — idade, macrociclo/mesociclo/semanas, observações, plano de treino (split semanal força/cardio) e dieta (refeições e macros), estes últimos por serem fatias futuras.
- `--simular` mostra exatamente o mesmo relatório sem gravar nada no banco.
- Casos de borda:
  - Pasta inexistente ou sem nenhum `.xlsx` → mensagem clara ("Nenhum arquivo .xlsx encontrado em ...") e código de saída 1, sem gravar nada.
  - Nenhum rótulo `atleta` encontrado → não cria o aluno; erro "Nome do aluno não encontrado nas planilhas." e saída 1.
  - Já existe aluno com o mesmo nome → não duplica; informa o id existente e sai sem gravar.
  - Erro de validação vindo do serviço (ex.: término anterior ao início na planilha) → mostra a mensagem do serviço e não grava.
- O comando roda as migrações antes de gravar (mesmo caminho de startup da aplicação), para funcionar num banco novo.

## Pré-condições
- Issues 01-09 concluídas (52 testes verdes).
- Dependência nova: `openpyxl` (hoje instalada na máquina, mas ainda não declarada no projeto).
- Pasta de validação real: `C:\Users\jeffr\OneDrive\Ambiente de Trabalho\consultoria\alunos\marcos anastasio\` com `MARCOS ANASTASIO.xlsx` e `marcos anastasio dieta.xlsx`.

## Arquivos a criar
- `kairos/alunos/excel_import.py` — leitura e interpretação das planilhas, sem banco e sem impressão: `parse_aluno_folder(folder) -> ParsedImport` (dataclass com `fields` dos campos reconhecidos, `not_imported` com pares item/motivo, e `warnings` das divergências). Inclui o normalizador de rótulos (sem acento/maiúsculas) e a extração de datas por regex.
- `kairos/cli.py` — interface de linha de comando com argparse: subcomando `importar-aluno`, flag `--simular`; chama `setup_logging()`, `run_migrations()`, o parser e o serviço; imprime o relatório em português; define os códigos de saída. Executável via `python -m kairos.cli`.
- `tests/test_importacao_excel.py` — testes com planilhas geradas em tmp_path imitando a estrutura real (rótulos em linhas diferentes, período com lixo entre as datas, nome com espaço duplo): campos reconhecidos; idade listada como não importada; pasta vazia; sem rótulo atleta; nome duplicado não duplica; `--simular` não grava; e um teste marcado `skipif` que roda contra a pasta real do Marcos quando ela existir na máquina.

## Arquivos a modificar
- `pyproject.toml` — acrescentar `openpyxl>=3.1` às dependências.
- `kairos/alunos/service.py` — nova função `find_aluno_by_name(name) -> dict | None` (busca exata, usada para não duplicar; a decisão fica no serviço, não no CLI).

## Camadas envolvidas
integração (leitura de arquivos externos), serviço, CLI, teste

## Status
concluída
