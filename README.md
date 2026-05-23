# Sistema de Gestão de Alunos — Personal Trainer

Sistema completo para personal trainers gerenciarem alunos, avaliações físicas, planos de treino e gerar relatórios automáticos com Inteligência Artificial.

**Ferramentas utilizadas:**
- **AppSheets** — app mobile para registrar dados pelo celular
- **Google Sheets** — banco de dados central (conectado ao AppSheets)
- **Google Drive** — onde fica o vault do Obsidian
- **Obsidian** — visualização dos relatórios e dossiê de cada aluno
- **Claude AI (Anthropic)** — gera relatórios, follow-ups e revisões de treino

**Fluxo do sistema:**

```
Celular (AppSheets)
        ↓
Google Sheets (banco de dados)
        ↓
Script Python (neste repositório)
        ↓
Claude AI → gera o relatório
        ↓
Google Drive → salva como .md
        ↓
Obsidian → você lê e usa o relatório
```

---

## Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Instalar Python](#2-instalar-python)
3. [Baixar o projeto](#3-baixar-o-projeto)
4. [Configurar o Google Cloud](#4-configurar-o-google-cloud)
5. [Criar e configurar o Google Sheets](#5-criar-e-configurar-o-google-sheets)
6. [Configurar o Google Drive para o Obsidian](#6-configurar-o-google-drive-para-o-obsidian)
7. [Configurar a API do Claude](#7-configurar-a-api-do-claude)
8. [Preencher o arquivo .env](#8-preencher-o-arquivo-env)
9. [Criar as abas no Sheets automaticamente](#9-criar-as-abas-no-sheets-automaticamente)
10. [Configurar o AppSheets](#10-configurar-o-appsheets)
11. [Configurar o Obsidian](#11-configurar-o-obsidian)
12. [Testar o sistema completo](#12-testar-o-sistema-completo)
13. [Como usar no dia a dia](#13-como-usar-no-dia-a-dia)
14. [Referência de comandos](#14-referência-de-comandos)
15. [Solução de problemas](#15-solução-de-problemas)

---

## 1. Pré-requisitos

Antes de começar, certifique-se de ter ou criar:

| Item | Link |
|------|------|
| Conta Google (Gmail) | https://accounts.google.com |
| Chave de API do Claude | https://console.anthropic.com |
| Python 3.9 ou superior | https://python.org/downloads |
| Git instalado | https://git-scm.com/downloads |
| Obsidian instalado | https://obsidian.md |

> **Importante:** Use a mesma conta Google em todas as etapas (Google Cloud, Google Sheets, Drive e AppSheets).

---

## 2. Instalar Python

### Windows

1. Acesse https://python.org/downloads e clique em **Download Python 3.x.x** (versão mais recente)
2. Execute o instalador baixado
3. **Marque a opção "Add Python to PATH"** antes de clicar em Install (essa etapa é obrigatória)
4. Clique em **Install Now**
5. Ao final, clique em **Close**

Para verificar se instalou corretamente, abra o **Prompt de Comando** (tecla Windows + R → digite `cmd` → Enter) e execute:

```
python --version
```

Deve aparecer algo como `Python 3.12.0`.

### macOS

1. Acesse https://python.org/downloads e baixe o instalador para macOS
2. Execute o arquivo `.pkg` baixado e siga as instruções
3. Abra o **Terminal** (Spotlight → Terminal) e verifique:

```
python3 --version
```

> No macOS, use `python3` no lugar de `python` em todos os comandos deste guia.

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3 python3-pip git -y
python3 --version
```

---

## 3. Baixar o projeto

Abra o terminal (ou Prompt de Comando no Windows) e execute:

```bash
git clone https://github.com/jeffreyarcanjoreis/claoud.git
cd claoud
```

### Instalar as dependências Python

```bash
pip install -r requirements.txt
```

> No macOS, use `pip3` no lugar de `pip`.

Aguarde a instalação concluir. Você verá mensagens como `Successfully installed anthropic-x.x.x ...`.

**O que foi instalado:**
- `anthropic` — biblioteca para chamar o Claude AI
- `google-api-python-client` — acesso ao Sheets e Drive
- `python-dotenv` — lê as variáveis de configuração
- `rich` — interface colorida no terminal

---

## 4. Configurar o Google Cloud

Esta etapa cria as credenciais que permitem o script Python acessar seus dados no Sheets e Drive.

### 4.1. Criar um projeto no Google Cloud Console

1. Acesse https://console.cloud.google.com
2. Se for a primeira vez, aceite os termos de serviço
3. No topo da página, clique em **"Selecionar projeto"** (ao lado do logo do Google Cloud)
4. Na janela que abrir, clique em **"Novo projeto"** (canto superior direito)
5. No campo **Nome do projeto**, escreva: `personal-trainer-system`
6. Deixe a organização como está e clique em **Criar**
7. Aguarde a criação (alguns segundos) e selecione o projeto recém-criado

### 4.2. Ativar a API do Google Sheets

1. No menu lateral esquerdo, clique em **"APIs e serviços"** → **"Biblioteca"**
2. No campo de busca, digite: `Google Sheets API`
3. Clique no resultado **"Google Sheets API"**
4. Clique no botão azul **"Ativar"**
5. Aguarde a ativação (página recarrega com o botão mostrando "Gerenciar")

### 4.3. Ativar a API do Google Drive

1. Clique em **"Biblioteca"** novamente (menu lateral ou botão na página)
2. Busque: `Google Drive API`
3. Clique em **"Google Drive API"**
4. Clique em **"Ativar"**

### 4.4. Configurar a tela de consentimento OAuth

> Essa etapa é necessária para que o Google permita que o script acesse sua conta.

1. No menu lateral, clique em **"APIs e serviços"** → **"Tela de consentimento OAuth"**
2. Selecione **"Externo"** e clique em **Criar**
3. Preencha os campos obrigatórios:
   - **Nome do app:** `Personal Trainer System`
   - **E-mail de suporte ao usuário:** seu e-mail do Gmail
   - **E-mail do desenvolvedor:** seu e-mail do Gmail
4. Clique em **Salvar e continuar** nas próximas três telas (Escopos, Usuários de teste, Resumo) sem alterar nada
5. Clique em **Voltar ao painel**

### 4.5. Criar as credenciais OAuth2

1. No menu lateral, clique em **"Credenciais"**
2. Clique em **"+ Criar credenciais"** (topo da página) → escolha **"ID do cliente OAuth"**
3. No campo **"Tipo de aplicativo"**, selecione **"App para computador"**
4. No campo **Nome**, escreva: `personal-trainer-cli`
5. Clique em **Criar**
6. Uma janela mostrará o ID e o segredo — clique em **"Baixar JSON"**
7. Renomeie o arquivo baixado para `credentials.json`
8. Mova o arquivo `credentials.json` para dentro da pasta `claoud` (a pasta do projeto)

> O arquivo ficará em: `claoud/credentials.json`

---

## 5. Criar e configurar o Google Sheets

### 5.1. Criar a planilha

1. Acesse https://sheets.google.com
2. Clique no botão **"+"** (em branco) para criar uma nova planilha
3. Clique no título "Planilha sem título" (canto superior esquerdo) e renomeie para:
   `Sistema de Gestão - Personal Trainer`
4. A planilha está criada

### 5.2. Copiar o ID da planilha

Olhe para a URL no navegador. Ela terá este formato:

```
https://docs.google.com/spreadsheets/d/AQUI_FICA_O_ID/edit#gid=0
```

O ID é a sequência de letras e números entre `/d/` e `/edit`. Exemplo:

```
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit
                                        ↑ este é o ID ↑
```

Copie e guarde esse ID — você vai precisar dele na etapa 8.

---

## 6. Configurar o Google Drive para o Obsidian

### 6.1. Localizar a pasta do vault no Drive

1. Acesse https://drive.google.com
2. Encontre a pasta onde está o seu vault do Obsidian
   - Se o vault está sincronizado com o Drive, a pasta já existe
   - Se não existe ainda, clique em **"+ Novo"** → **"Nova pasta"** e crie uma chamada `Obsidian Vault`
3. Abra a pasta e clique em **"Alunos"** (crie essa subpasta se não existir — é onde os relatórios serão salvos)
   - Alternativamente, use a pasta raiz do vault

### 6.2. Copiar o ID da pasta

Com a pasta aberta, olhe para a URL:

```
https://drive.google.com/drive/folders/AQUI_FICA_O_ID_DA_PASTA
```

Copie o ID (a parte após `/folders/`) e guarde — você vai precisar na etapa 8.

---

## 7. Configurar a API do Claude

1. Acesse https://console.anthropic.com
2. Faça login (ou crie uma conta caso não tenha)
3. No menu lateral, clique em **"API Keys"**
4. Clique em **"Create Key"**
5. Dê um nome à chave: `personal-trainer-system`
6. Clique em **"Create Key"**
7. Copie a chave exibida (começa com `sk-ant-...`)

> **Atenção:** A chave só é exibida uma vez. Guarde em local seguro antes de fechar a janela.

> **Sobre custos:** A API do Claude cobra por uso. Para o volume típico de um personal trainer (poucos relatórios por dia), o custo mensal fica em torno de U$ 1–3. Você pode ver o consumo em **"Usage"** no console.

---

## 8. Preencher o arquivo .env

O arquivo `.env` guarda todas as suas credenciais e configurações. Ele nunca é enviado ao GitHub.

### 8.1. Criar o arquivo

Na pasta `claoud`, execute:

```bash
cp .env.example .env
```

### 8.2. Editar o arquivo

Abra o arquivo `.env` com qualquer editor de texto (Bloco de Notas, VS Code, etc.) e preencha cada linha:

```env
# Chave da API do Claude (copiada na etapa 7)
ANTHROPIC_API_KEY=sk-ant-SUA_CHAVE_AQUI

# ID da planilha Google Sheets (copiado na etapa 5.2)
GOOGLE_SHEETS_ID=SEU_ID_DO_SHEETS_AQUI

# ID da pasta no Google Drive (copiado na etapa 6.2)
GOOGLE_DRIVE_VAULT_FOLDER_ID=SEU_ID_DA_PASTA_AQUI

# Caminho para o arquivo de credenciais (deixe assim se o arquivo está na raiz do projeto)
GOOGLE_CREDENTIALS_PATH=./credentials.json
```

Salve o arquivo.

---

## 9. Criar as abas no Sheets automaticamente

Com tudo configurado, execute o script que cria todas as abas e cabeçalhos na planilha:

```bash
python sheets/setup_sheets.py
```

### O que acontece na primeira execução

1. O terminal exibirá: `Abrindo navegador para autenticação do Google...`
2. Uma janela do navegador abrirá pedindo para você fazer login na sua conta Google
3. Clique em sua conta → clique em **"Avançado"** → clique em **"Acessar personal-trainer-system (não seguro)"**
   > Essa mensagem aparece porque o app está em modo de teste. É seguro prosseguir.
4. Clique em **"Continuar"** para dar permissão de acesso ao Sheets e Drive
5. O navegador exibirá: `A autenticação foi concluída. Pode fechar esta aba.`
6. Volte ao terminal — o script continuará e criará as abas

### Resultado esperado

O script criará as seguintes abas na sua planilha:

| Aba | O que armazena |
|-----|----------------|
| `Alunos` | Cadastro completo de cada aluno |
| `Avaliacoes` | Histórico de avaliações físicas com medidas |
| `Planos_Treino` | Planos de treino criados |
| `Exercicios` | Exercícios detalhados de cada plano |
| `Sessoes` | Registro de presença e disposição por sessão |
| `Follow_ups` | Registro dos follow-ups gerados pela IA |

Abra a planilha no Sheets e confirme que as abas foram criadas com os cabeçalhos.

---

## 10. Configurar o AppSheets

O AppSheets é o app mobile que você vai usar para registrar dados dos alunos pelo celular, conectado diretamente à planilha Google Sheets.

### 10.1. Criar a conta e o app

1. Acesse https://appsheet.com
2. Clique em **"Sign in with Google"** e faça login com a **mesma conta Google** da planilha
3. Após o login, clique em **"+ Create"** → **"App"** → **"Start with your own data"**
4. Clique em **"Google Sheets"**
5. Selecione a planilha `Sistema de Gestão - Personal Trainer`
6. Selecione a aba **"Alunos"** como ponto de partida
7. Clique em **"Customize with AppSheet"**

O AppSheets criará um app básico automaticamente. Agora vamos configurar cada tabela.

### 10.2. Configurar as tabelas

No painel do AppSheets, clique em **"Data"** no menu lateral esquerdo. Você verá as tabelas detectadas automaticamente. Adicione as que faltarem e configure os tipos de cada coluna conforme abaixo.

Para adicionar uma tabela que não aparecer: clique em **"+ Add Table"** → selecione a aba correspondente no Sheets.

---

**Tabela: Alunos**

| Coluna | Tipo no AppSheets | Observação |
|--------|------------------|------------|
| id | Text | Marque como **Key** (chave) |
| nome | Text | |
| idade | Number | |
| sexo | Enum | Valores: `Masculino`, `Feminino` |
| whatsapp | Phone | |
| email | Email | |
| data_inicio | Date | |
| plano | Enum | Valores: `mensal`, `trimestral`, `semestral` |
| frequencia_semanal | Number | |
| status | Enum | Valores: `ativo`, `inativo` |
| objetivo_principal | Text | |
| observacoes | LongText | |

---

**Tabela: Avaliacoes**

| Coluna | Tipo no AppSheets | Observação |
|--------|------------------|------------|
| id | Text | Marque como **Key** |
| id_aluno | Ref | Referência para tabela **Alunos** |
| nome_aluno | Text | |
| data | Date | |
| peso_kg | Decimal | |
| percentual_gordura | Decimal | |
| massa_magra_kg | Decimal | |
| cintura_cm | Decimal | |
| quadril_cm | Decimal | |
| peito_cm | Decimal | |
| braco_d_cm | Decimal | |
| braco_e_cm | Decimal | |
| coxa_d_cm | Decimal | |
| coxa_e_cm | Decimal | |
| observacoes | LongText | |

---

**Tabela: Sessoes**

| Coluna | Tipo no AppSheets | Observação |
|--------|------------------|------------|
| id | Text | Marque como **Key** |
| id_aluno | Ref | Referência para tabela **Alunos** |
| nome_aluno | Text | |
| data | Date | |
| presente | Enum | Valores: `sim`, `nao` |
| disposicao | Number | Escala de 1 a 5 |
| observacoes_sessao | LongText | |

---

**Tabela: Planos_Treino**

| Coluna | Tipo no AppSheets | Observação |
|--------|------------------|------------|
| id | Text | Marque como **Key** |
| id_aluno | Ref | Referência para tabela **Alunos** |
| nome_aluno | Text | |
| nome_treino | Text | Ex: "Treino de Hipertrofia - Fase 1" |
| data_criacao | Date | |
| fase | Text | Ex: "Fase 1", "Manutenção" |
| objetivo_treino | Text | |
| status | Enum | Valores: `ativo`, `arquivado` |

---

**Tabela: Exercicios**

| Coluna | Tipo no AppSheets | Observação |
|--------|------------------|------------|
| id | Text | Marque como **Key** |
| id_plano | Ref | Referência para tabela **Planos_Treino** |
| id_aluno | Ref | Referência para tabela **Alunos** |
| grupo_muscular | Text | Ex: "Peito", "Costas" |
| exercicio | Text | Ex: "Supino Reto com Barra" |
| series | Number | |
| repeticoes | Text | Ex: "8-12" ou "15" |
| carga_kg | Decimal | |
| descanso_seg | Number | Em segundos |
| observacoes | LongText | |

### 10.3. Criar as views (telas do app)

As views são as telas que aparecerão no seu app. Clique em **"Views"** no menu lateral.

Para criar uma nova view: clique em **"+ Add View"**, escolha o nome, tipo e tabela.

| Nome da view | Tipo | Tabela | Para que serve |
|---|---|---|---|
| Alunos | Gallery ou List | Alunos | Lista de todos os alunos |
| Detalhe do Aluno | Detail | Alunos | Ver todos os dados do aluno |
| Nova Avaliação | Form | Avaliacoes | Registrar avaliação física |
| Registrar Sessão | Form | Sessoes | Marcar presença/falta diária |
| Planos de Treino | List | Planos_Treino | Ver planos criados |
| Novo Exercício | Form | Exercicios | Adicionar exercício ao plano |

> **Dica:** Na view "Detalhe do Aluno", adicione views inline de `Avaliacoes` e `Sessoes`. Para isso: abra a view Detail → seção "Inline Views" → adicione as duas tabelas. Assim você vê o histórico do aluno em uma tela só.

### 10.4. Publicar o app e instalar no celular

1. Clique em **"Save"** no topo da página para salvar todas as configurações
2. Clique em **"Deploy"** → **"Deploy app"** para publicar
3. No celular, abra o navegador e acesse o link do app fornecido pelo AppSheets
   — ou instale o app **AppSheets** da Play Store / App Store e faça login

---

## 11. Configurar o Obsidian

### 11.1. Apontar o vault para o Google Drive

Se o seu vault do Obsidian já está na pasta do Google Drive sincronizada:
1. Abra o Obsidian
2. Clique em **"Abrir outra pasta como vault"**
3. Navegue até a pasta do Google Drive onde fica o vault
4. Clique em **"Abrir"**

### 11.2. Instalar o plugin Templater

O Templater é necessário para usar os templates de aluno, avaliação e plano de treino.

1. No Obsidian, vá em **Configurações** (ícone de engrenagem) → **Plugins da comunidade**
2. Clique em **"Ativar plugins da comunidade"** se ainda não estiver ativado
3. Clique em **"Procurar"** e busque por: `Templater`
4. Clique em **Instalar** → depois em **Ativar**
5. Nas configurações do Templater, defina a **"Pasta de templates"** como: `templates` (ou o caminho onde você colocar os arquivos da pasta `templates/obsidian/`)

### 11.3. Copiar os templates para o vault

Copie os três arquivos da pasta `templates/obsidian/` deste projeto para dentro do seu vault do Obsidian (na pasta que você definiu como pasta de templates):

- `aluno.md` → template para criar a nota de um novo aluno
- `avaliacao.md` → template para registrar avaliações
- `plano_treino.md` → template para montar planos de treino

### 11.4. Criar a estrutura de pastas no vault (recomendado)

Dentro do vault, crie a seguinte estrutura:

```
Obsidian Vault/
├── Alunos/          ← onde ficam as notas dos alunos
├── Relatórios/      ← onde o script salva os relatórios gerados
├── Avaliações/      ← avaliações criadas manualmente no Obsidian
└── templates/       ← os templates copiados na etapa anterior
```

> Aponte o `GOOGLE_DRIVE_VAULT_FOLDER_ID` no `.env` para a pasta `Relatórios/` no Drive, para os relatórios gerados pela IA aparecerem organizados.

---

## 12. Testar o sistema completo

### 12.1. Cadastrar um aluno de teste

1. Abra o AppSheets no celular (ou no navegador)
2. Vá na view **"Alunos"** → toque em **"+"** para adicionar
3. Preencha os dados:
   - **id:** `ALU001`
   - **nome:** `João Silva`
   - **idade:** `28`
   - **status:** `ativo`
   - **objetivo_principal:** `Hipertrofia muscular`
4. Salve

### 12.2. Registrar uma avaliação de teste

1. No AppSheets → view **"Nova Avaliação"**
2. Preencha:
   - **id:** `AVA001`
   - **id_aluno:** `ALU001`
   - **nome_aluno:** `João Silva`
   - **data:** data de hoje
   - **peso_kg:** `80`
   - **percentual_gordura:** `18`
   - Preencha algumas medidas (cintura, quadril, etc.)
3. Salve

### 12.3. Gerar o primeiro relatório

No terminal, dentro da pasta `claoud`, execute:

```bash
python scripts/generate_report.py --aluno "João Silva" --tipo relatorio
```

**O que acontece:**
1. O script busca todos os dados de João Silva no Sheets
2. Monta um resumo estruturado e envia para o Claude AI
3. O Claude gera o relatório em português
4. O relatório é salvo como `.md` no Google Drive
5. O conteúdo do relatório aparece no terminal em cores

**Resultado esperado no terminal:**
```
Buscando dados de "João Silva" no Sheets...
✓ Aluno encontrado: João Silva (ALU001)
✓ 1 avaliação carregada
Gerando relatório com Claude AI...
✓ Relatório gerado
Salvando no Google Drive...
✓ Arquivo salvo: joao_silva_relatorio_2024-03-15.md
```

### 12.4. Ver o relatório no Obsidian

1. Abra o Obsidian
2. Aguarde a sincronização com o Google Drive (pode levar alguns segundos)
3. Navegue até a pasta `Relatórios/`
4. O arquivo `joao_silva_relatorio_2024-03-15.md` estará lá

---

## 13. Como usar no dia a dia

### Rotina diária (celular)

**Antes ou durante o treino:**
1. Abra o AppSheets
2. Selecione o aluno na view **"Alunos"**
3. Toque em **"Registrar Sessão"**
4. Preencha: presente (sim/não), disposição (1–5), observações rápidas
5. Salve — o dado vai direto para o Sheets

### A cada avaliação física

1. No AppSheets → **"Nova Avaliação"**
2. Preencha todas as medidas corporais
3. Salve

Quanto mais avaliações registradas, **mais rico e preciso** o relatório gerado pela IA.

### Geração de relatórios (computador)

Depois de ter dados suficientes no Sheets, gere relatórios com os comandos abaixo.

**Relatório completo de evolução:**
```bash
python scripts/generate_report.py --aluno "Nome do Aluno" --tipo relatorio
```

O Claude compara avaliações ao longo do tempo, analisa aderência ao objetivo, destaca progressos e pontos de atenção.

**Mensagem de follow-up:**
```bash
python scripts/generate_report.py --aluno "Nome do Aluno" --tipo followup
```

O Claude gera uma mensagem personalizada, considerando o histórico do aluno, pronta para você copiar e enviar pelo WhatsApp.

**Revisão do plano de treino:**
```bash
python scripts/generate_report.py --aluno "Nome do Aluno" --tipo treino
```

O Claude analisa o plano atual e sugere ajustes com base na evolução registrada.

---

## 14. Referência de comandos

```bash
# Relatório de progresso
python scripts/generate_report.py --aluno "João Silva" --tipo relatorio

# Follow-up personalizado
python scripts/generate_report.py --aluno "João Silva" --tipo followup

# Revisão do treino
python scripts/generate_report.py --aluno "João Silva" --tipo treino

# Busca parcial (funciona sem acento e com parte do nome)
python scripts/generate_report.py --aluno "joao" --tipo relatorio

# Busca pelo ID exato
python scripts/generate_report.py --aluno ALU001 --tipo followup

# Configurar abas do Sheets (rodar apenas uma vez)
python sheets/setup_sheets.py
```

---

## 15. Solução de problemas

**"python não é reconhecido como comando"**
- Windows: refaça a instalação do Python marcando a opção "Add Python to PATH"
- macOS/Linux: use `python3` no lugar de `python`

**"Arquivo credentials.json não encontrado"**
- Verifique se o arquivo `credentials.json` está dentro da pasta `claoud/`
- Confirme que o caminho em `GOOGLE_CREDENTIALS_PATH` no `.env` está correto (`./credentials.json`)

**Janela de autenticação Google não abre**
- Execute novamente o script — às vezes demora um segundo
- Se o browser não abrir, copie a URL exibida no terminal e cole manualmente no navegador

**"Acesso bloqueado: este app não é verificado pelo Google"**
- Clique em **"Avançado"** → **"Acessar personal-trainer-system (não seguro)"**
- Isso aparece porque o app está em modo de teste no Google Cloud — é seguro

**"GOOGLE_SHEETS_ID não encontrado"**
- Verifique se o arquivo `.env` existe (não apenas `.env.example`)
- Confirme que o ID da planilha foi colado corretamente, sem espaços extras

**"Aluno não encontrado"**
- O nome buscado deve corresponder ao campo `nome` na aba `Alunos` do Sheets
- Tente buscar com parte do nome: `--aluno "João"` em vez do nome completo
- Confirme que o aluno foi cadastrado via AppSheets e que os dados apareceram no Sheets

**Erro de autenticação após funcionar antes**
- Delete o arquivo `token.json` (gerado automaticamente na pasta do projeto)
- Execute o script novamente para refazer a autenticação

**Relatório gerado em outro idioma ou sem contexto**
- Verifique se os dados no Sheets estão preenchidos corretamente (nome, objetivo, avaliações)
- Quanto mais dados registrados, melhor a qualidade do relatório

**Script trava sem resposta**
- Verifique sua conexão com a internet
- Confira se a chave `ANTHROPIC_API_KEY` no `.env` está correta e ativa

---

## Estrutura do projeto

```
claoud/
├── .env.example              # Modelo do arquivo de configuração
├── .env                      # Suas credenciais (NÃO commitar)
├── credentials.json          # Credenciais Google OAuth2 (NÃO commitar)
├── token.json                # Token salvo automaticamente (NÃO commitar)
├── requirements.txt          # Dependências Python
├── README.md                 # Este guia
├── sheets/
│   ├── schema.json           # Definição das abas e colunas
│   └── setup_sheets.py       # Cria as abas no Sheets automaticamente
├── scripts/
│   ├── google_client.py      # Conexão com Google Sheets e Drive
│   └── generate_report.py    # Gera relatórios via Claude AI
└── templates/
    └── obsidian/
        ├── aluno.md          # Template de nota de aluno
        ├── avaliacao.md      # Template de avaliação física
        └── plano_treino.md   # Template de plano de treino
```

---

## Segurança

Os arquivos abaixo contêm credenciais e **nunca devem ser enviados ao GitHub**. Eles já estão listados no `.gitignore`:

```
.env
credentials.json
token.json
```

Antes de qualquer `git push`, confirme com `git status` que esses arquivos não aparecem como "alterações para commitar".
