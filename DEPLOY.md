# Colocar o Kairos no ar (Render + Supabase)

O app roda no **Render**. Banco e login ficam no **Supabase** que você já tem
(anotado no vault "kairos 3.0"). A configuração do Render está pronta em
`render.yaml`; o `Dockerfile` monta a imagem.

## 0. Antes de começar — duas confirmações

1. **Onde estão seus dados hoje?**
   - Se o seu `.env` local tem `KAIROS_DATABASE_URL` apontando para o
     Supabase, seus alunos já estão lá e vão aparecer no app online.
   - Se não tem, seus dados estão num arquivo do seu computador
     (`data/kairos.db`) e o app online começa vazio. Me avise para decidirmos
     se levamos esses dados ou se você começa do zero com os alunos reais.
2. **Sua conta de coach.** O sistema transforma o **primeiro login** em
   coach. Se você já entrou como coach usando este mesmo Supabase, está tudo
   pronto. Se o banco estiver vazio, **faça o seu login logo depois do
   primeiro deploy**, antes de passar o endereço para qualquer pessoa.

## 1. Separe três valores do Supabase

Use os **mesmos valores do seu `.env` local** (já testados), com uma exceção
no endereço do banco:

| Variável no Render | Onde pegar |
|---|---|
| `KAIROS_SUPABASE_URL` | Supabase → Settings → API → **Project URL** |
| `KAIROS_SUPABASE_ANON_KEY` | Supabase → Settings → API → chave **anon public** (a mesma do seu `.env`) |
| `KAIROS_DATABASE_URL` | Supabase → botão **Connect** → aba **Session pooler** → copie e troque `[YOUR-PASSWORD]` pela senha do banco |

> **Por que "Session pooler" e não "Direct connection":** a conexão direta do
> Supabase usa IPv6, e o Render só conecta por IPv4. Com a direta, o app não
> alcança o banco.

Esses valores **não** vão no chat nem em arquivo do repositório — só no
painel do Render.

## 2. Crie o serviço no Render

1. Crie a conta em render.com e conecte o seu GitHub.
2. **New → Blueprint** → escolha o repositório `claoud` e a branch (veja a
   nota abaixo). O Render lê o `render.yaml` sozinho.
3. Ele pede os valores marcados como `sync: false`: cole os três do passo 1.
   `KAIROS_GCAL_ICS_URL` é opcional (link secreto do Google Calendar).
4. Confirme o plano **Starter** com o disco **kairos-data (1 GB)**. É o disco
   que guarda fotos, vídeos e anexos — sem ele, os arquivos somem a cada
   atualização.
5. **Apply**. O primeiro deploy leva alguns minutos.

> **Branch:** hoje o código está na branch
> `docs/add-contributing-section-463f65`. O ideal é publicá-la na `main`
> antes (eu abro o pull request quando você pedir) e apontar o Render para a
> `main`.
>
> **Região:** o `render.yaml` usa Frankfurt (perto de Lisboa). Se o seu
> projeto Supabase estiver em outra região, me avise para ajustarmos.

## 3. Confira se subiu

- Em **Logs**, procure a linha `Kairos application started.`
- Se aparecer **"Configuração de produção insegura"**, a própria mensagem
  lista o que falta. Corrija em **Environment** e clique **Manual Deploy**.
- Se aparecer erro de **SSL** ao conectar no banco, adicione
  `KAIROS_DATABASE_SSL=disable` em Environment para destravar e me avise (a
  conexão fica sem criptografia até resolvermos).
- Abra `https://<seu-serviço>.onrender.com/login` e entre como coach.

## 4. Ajuste o Supabase para o novo endereço

Sem isso, "Esqueci minha senha" e a ativação de alunos apontam para o
endereço errado. Supabase → **Authentication → URL Configuration**:

- **Site URL:** `https://<seu-serviço>.onrender.com`
- **Redirect URLs:** adicione `https://<seu-serviço>.onrender.com/redefinir-senha`

## 5. Teste rápido (5 minutos)

1. Cadastre um aluno.
2. Agende uma sessão e registre-a como realizada.
3. Defina o plano do aluno e lance um recebimento.
4. Abra **Financeiro** e confira o painel do mês.

## Atualizações

O deploy automático está desligado (`autoDeploy: false`), para nada ir ao ar
sem você saber. Depois de cada mudança publicada: **Manual Deploy → Deploy
latest commit**.

## Custos aproximados

- **Render Starter:** por volta de US$ 7/mês, mais o disco (centavos por GB).
- **Supabase:** o plano gratuito serve para começar. Projetos gratuitos podem
  ser pausados depois de um tempo sem uso; com uso diário isso não acontece.

## Segurança que já vem embutida

- Em produção o app **se recusa a iniciar** com o login desligado
  (`KAIROS_DEV_NO_AUTH`), sem chave secreta, sem banco na nuvem ou sem
  Supabase — e diz o que falta.
- A conexão com o banco é **criptografada** (TLS): dados de saúde dos alunos
  não trafegam em texto puro.
- A chave de sessão é gerada pelo Render; nenhum segredo fica no repositório.
