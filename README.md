# Sistema de Gestão de Alunos — Personal Trainer

Sistema completo para personal trainers gerenciarem alunos, avaliações físicas, planos de treino e geração automática de relatórios com Inteligência Artificial.

**Fluxo principal:**

```
AppSheets (mobile) → Google Sheets (banco de dados)
                          ↓
               Script Python + Claude API
                          ↓
         Google Drive / Obsidian vault (relatórios .md)
```

---

## O que este sistema faz

- **Cadastro pelo celular:** via AppSheets, você registra alunos, avaliações físicas, sessões e planos de treino diretamente do smartphone, sem abrir o computador.
- **Banco de dados em Google Sheets:** todos os dados ficam organizados em abas separadas (Alunos, Avaliações, Planos de Treino, Exercícios, Sessões, Follow-ups).
- **Relatórios com IA:** um script Python lê os dados do aluno no Sheets, envia para o Claude (IA da Anthropic) e gera:
  - Relatório de progresso completo com comparativo entre avaliações
  - Mensagem de follow-up personalizada para enviar ao aluno
  - Revisão do plano de treino com sugestões de ajuste
- **Vault Obsidian no Drive:** os relatórios são salvos como arquivos Markdown no Google Drive, prontos para abrir no Obsidian.

---

## Pré-requisitos

- Python 3.9 ou superior
- Conta Google (Gmail) com acesso ao Google Cloud Console
- Chave de API da Anthropic (Claude)
- Aplicativo Obsidian instalado (opcional, mas recomendado)
- Conta no AppSheets (plano gratuito funciona para uso básico)

---

## Instalação

### 1. Clone o repositório e instale as dependências

```bash
git clone <url-do-repositorio>
cd claoud
pip install -r requirements.txt
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Abra o arquivo `.env` e preencha cada variável (veja detalhes nas seções abaixo).

---

## Configuração do Google Cloud

### 2.1. Crie um projeto no Google Cloud Console

1. Acesse [console.cloud.google.com](https://console.cloud.google.com/)
2. Clique em **Selecionar projeto** → **Novo projeto**
3. Dê um nome (ex: `personal-trainer-system`) e clique em **Criar**

### 2.2. Ative as APIs necessárias

No menu lateral, vá em **APIs e serviços** → **Biblioteca** e ative:
- **Google Sheets API**
- **Google Drive API**

### 2.3. Crie as credenciais OAuth2

1. Vá em **APIs e serviços** → **Credenciais**
2. Clique em **+ Criar credenciais** → **ID do cliente OAuth**
3. Tipo de aplicativo: **Aplicativo para computador**
4. Dê um nome e clique em **Criar**
5. Clique em **Baixar JSON** e salve o arquivo como `credentials.json` na raiz do projeto
6. No `.env`, defina: `GOOGLE_CREDENTIALS_PATH=./credentials.json`

> Na primeira execução de qualquer script, uma janela do navegador abrirá pedindo autorização. Após autorizar, um arquivo `token.json` será salvo automaticamente para as próximas execuções.

---

## Configuração do Google Sheets

### 2.4. Crie a planilha

1. Acesse [sheets.google.com](https://sheets.google.com) e crie uma nova planilha em branco
2. Dê um nome (ex: `Sistema de Gestão - Personal Trainer`)
3. Copie o ID da planilha da URL:
   ```
   https://docs.google.com/spreadsheets/d/  <<ESTE_TRECHO_É_O_ID>>  /edit
   ```
4. No `.env`, defina: `GOOGLE_SHEETS_ID=<id-copiado>`

### 2.5. Configure as abas automaticamente

Execute o script de configuração para criar todas as abas e cabeçalhos:

```bash
python sheets/setup_sheets.py
```

Esse script cria as seguintes abas com os cabeçalhos corretos:

| Aba | Descrição |
|-----|-----------|
| `Alunos` | Cadastro dos alunos |
| `Avaliacoes` | Histórico de avaliações físicas |
| `Planos_Treino` | Planos de treino criados |
| `Exercicios` | Exercícios de cada plano |
| `Sessoes` | Registro de presença e disposição |
| `Follow_ups` | Follow-ups gerados pela IA |

---

## Configuração do Google Drive (Vault Obsidian)

### 2.6. Crie a pasta no Drive

1. Acesse [drive.google.com](https://drive.google.com)
2. Crie uma pasta chamada `Obsidian Vault` (ou o nome do seu vault)
3. Abra a pasta e copie o ID da URL:
   ```
   https://drive.google.com/drive/folders/  <<ESTE_TRECHO_É_O_ID>>
   ```
4. No `.env`, defina: `GOOGLE_DRIVE_VAULT_FOLDER_ID=<id-copiado>`

### 2.7. Sincronize com o Obsidian (opcional)

- **No computador:** use o aplicativo Google Drive para Desktop para sincronizar a pasta localmente. Aponte o vault do Obsidian para essa pasta.
- **No celular:** use o plugin **Obsidian Sync** ou **Remotely Save** com Google Drive.

---

## Configuração da API do Claude (Anthropic)

1. Acesse [console.anthropic.com](https://console.anthropic.com/)
2. Vá em **API Keys** → **Create Key**
3. Copie a chave e no `.env` defina: `ANTHROPIC_API_KEY=sk-ant-...`

---

## Configuração do AppSheets

O AppSheets é o aplicativo mobile que conecta ao Google Sheets e permite registrar dados pelo celular.

### 3.1. Crie o app

1. Acesse [appsheet.com](https://appsheet.com) e faça login com a mesma conta Google
2. Clique em **+ New App** → **Start with your own data**
3. Selecione a planilha Google Sheets que você criou
4. O AppSheets detectará automaticamente as abas

### 3.2. Tabelas e colunas necessárias

Configure as seguintes tabelas no AppSheets (o sistema já cria as colunas no Sheets):

**Tabela: Alunos**
| Coluna | Tipo AppSheets |
|--------|---------------|
| id | Text (chave) |
| nome | Text |
| idade | Number |
| sexo | Enum (Masculino, Feminino) |
| whatsapp | Phone |
| email | Email |
| data_inicio | Date |
| plano | Enum (mensal, trimestral, semestral) |
| frequencia_semanal | Number |
| status | Enum (ativo, inativo) |
| objetivo_principal | Text |
| observacoes | LongText |

**Tabela: Avaliacoes**
| Coluna | Tipo AppSheets |
|--------|---------------|
| id | Text (chave) |
| id_aluno | Ref → Alunos |
| nome_aluno | Text |
| data | Date |
| peso_kg | Decimal |
| percentual_gordura | Decimal |
| massa_magra_kg | Decimal |
| cintura_cm | Decimal |
| quadril_cm | Decimal |
| peito_cm | Decimal |
| braco_d_cm | Decimal |
| braco_e_cm | Decimal |
| coxa_d_cm | Decimal |
| coxa_e_cm | Decimal |
| observacoes | LongText |

**Tabela: Sessoes**
| Coluna | Tipo AppSheets |
|--------|---------------|
| id | Text (chave) |
| id_aluno | Ref → Alunos |
| nome_aluno | Text |
| data | Date |
| presente | Enum (sim, nao) |
| disposicao | Number (1–5) |
| observacoes_sessao | LongText |

**Tabela: Exercicios**
| Coluna | Tipo AppSheets |
|--------|---------------|
| id | Text (chave) |
| id_plano | Ref → Planos_Treino |
| id_aluno | Ref → Alunos |
| grupo_muscular | Text |
| exercicio | Text |
| series | Number |
| repeticoes | Text |
| carga_kg | Decimal |
| descanso_seg | Number |
| observacoes | LongText |

### 3.3. Views recomendadas no AppSheets

Configure estas views para facilitar o uso diário:

| View | Tipo | Tabela | Descrição |
|------|------|--------|-----------|
| **Alunos** | List | Alunos | Lista de todos os alunos ativos |
| **Detalhe do Aluno** | Detail | Alunos | Perfil completo com histórico |
| **Nova Avaliação** | Form | Avaliacoes | Formulário de avaliação física |
| **Registrar Sessão** | Form | Sessoes | Marcar presença/falta rápido |
| **Novo Exercício** | Form | Exercicios | Adicionar exercício ao plano |
| **Follow-ups** | List | Follow_ups | Ver follow-ups pendentes de envio |

> **Dica:** Na view "Detalhe do Aluno", adicione inline views de Avaliações e Sessões para ver o histórico do aluno em uma única tela.

---

## Como usar no dia a dia

### Fluxo diário

1. **Antes/durante o treino (celular):**
   - Abra o AppSheets
   - Selecione o aluno
   - Registre a sessão: presença, disposição (1–5), observações
   
2. **A cada avaliação (celular):**
   - No AppSheets → Nova Avaliação
   - Preencha todas as medidas corporais

3. **Geração de relatórios (computador):**

```bash
# Relatório completo de progresso
python scripts/generate_report.py --aluno "João Silva" --tipo relatorio

# Mensagem de follow-up personalizada
python scripts/generate_report.py --aluno "João Silva" --tipo followup

# Revisão do plano de treino
python scripts/generate_report.py --aluno ALU001 --tipo treino
```

O script irá:
- Buscar todos os dados do aluno no Google Sheets
- Enviar para o Claude AI para análise
- Salvar o relatório como `.md` no Google Drive (pasta do Obsidian)
- Exibir o conteúdo gerado no terminal

### Identificando o aluno

Você pode usar o **nome** (busca parcial, sem acento):
```bash
python scripts/generate_report.py --aluno "João" --tipo followup
```

Ou o **ID exato** da planilha (ex: ALU001):
```bash
python scripts/generate_report.py --aluno ALU001 --tipo relatorio
```

### Arquivo gerado

Os arquivos são salvos no Google Drive com o formato:
```
{nome_aluno}_{tipo}_{YYYY-MM-DD}.md
```

Exemplo: `joao_silva_relatorio_2024-03-15.md`

Cada arquivo inclui **frontmatter Obsidian** com tags automáticas para facilitar a organização no vault.

---

## Templates do Obsidian

Os templates na pasta `templates/obsidian/` podem ser usados diretamente no Obsidian com o plugin **Templater** ou o sistema nativo de templates:

| Template | Uso |
|----------|-----|
| `aluno.md` | Nota principal do aluno no vault |
| `avaliacao.md` | Registro de avaliação física |
| `plano_treino.md` | Plano de treino com tabelas A/B/C |

Para usar: no Obsidian, vá em **Configurações → Templates** e aponte para a pasta `templates/obsidian/`.

---

## Estrutura do projeto

```
claoud/
├── .env.example              # Template de variáveis de ambiente
├── .env                      # Suas credenciais (não commitar!)
├── credentials.json          # OAuth2 Google (não commitar!)
├── token.json                # Token salvo automaticamente (não commitar!)
├── requirements.txt          # Dependências Python
├── README.md                 # Este arquivo
├── sheets/
│   ├── schema.json           # Estrutura completa das abas do Sheets
│   └── setup_sheets.py       # Script para criar abas e cabeçalhos
├── scripts/
│   ├── google_client.py      # Helper: autenticação e acesso às APIs Google
│   └── generate_report.py    # Script principal de geração de relatórios
└── templates/
    └── obsidian/
        ├── aluno.md          # Template de nota de aluno
        ├── avaliacao.md      # Template de avaliação física
        └── plano_treino.md   # Template de plano de treino
```

---

## Troubleshooting

**"Arquivo de credenciais não encontrado"**
- Verifique se o `credentials.json` está no caminho indicado em `GOOGLE_CREDENTIALS_PATH` no `.env`

**"GOOGLE_SHEETS_ID não encontrado"**
- Confirme que o `.env` existe (não só o `.env.example`) e que o ID foi preenchido corretamente

**"Aluno não encontrado"**
- O nome da busca deve corresponder ao campo `nome` na aba `Alunos` do Sheets
- Tente buscar por uma parte do nome ou use o ID (ex: ALU001)
- Verifique se o aluno foi cadastrado pelo AppSheets e se os dados sincronizaram

**Erro de autenticação Google**
- Delete o arquivo `token.json` e execute novamente para refazer a autenticação

**Rate limit da API do Claude**
- O script usa o modelo `claude-sonnet-4-6`. Se atingir o limite, aguarde alguns minutos e tente novamente.

---

## Segurança

Os seguintes arquivos **nunca devem ser commitados** no Git:

```
.env
credentials.json
token.json
```

Esses arquivos já estão listados no `.gitignore`. Confirme antes de fazer qualquer push.
