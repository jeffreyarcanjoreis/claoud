# 32 — Link de ativação: o aluno cria o próprio acesso

Evolução do épico de login (issue [26](done/26-login-autenticacao.md), já concluído).
Substitui o passo manual "coach cria o usuário no painel do Supabase" por um
**link de ativação** que o coach gera na ficha e envia ao aluno; o aluno abre e
**define a própria senha**, criando a conta no Supabase na hora.

## Status
concluída

## Decisão do PO
Link seguro + o aluno cria a senha (não o convite automático por e-mail). O **coach
entrega o link** (WhatsApp/etc.); o app **não** envia e-mail. Sem segredo novo (usa o
`itsdangerous`/`secret_key` já existentes + o `anon key`), sem SMTP.

## Segurança / princípios
- A senha do aluno é digitada **por ele**, num formulário que a repassa direto ao
  Supabase Auth (signup) por HTTPS — o app **nunca** guarda nem loga a senha (mesmo
  padrão do login da Fase 1). Nem o coach nem qualquer operador veem a senha.
- O link é um **token assinado e com validade** (não adivinhável, expira). Amarrado a
  um `aluno_id`.
- Ativação é **idempotente/单-uso na prática**: se o aluno já tem `Perfil`, o link não
  cria outro — mostra "acesso já criado, é só entrar".
- Uma conta criada no Supabase sem `Perfil` continua **sem acesso** no app (o
  resolver devolve None) — então mesmo que alguém faça signup por fora, não entra.

## Especificação funcional

### Coach: gerar o link (na ficha do aluno)
1. Na seção "Acesso ao app" da ficha (`ficha.html`), quando o aluno tem **e-mail**
   cadastrado e **ainda não tem perfil** (estado "Aguardando 1º login"), aparece um
   **link de ativação** pronto (`{base}/ativar/{token}`) num campo copiável + um texto
   curto "Envie este link para o aluno criar o acesso (validade: N dias)".
2. Quando o acesso já está ativo (perfil existe) → não mostra link (mostra "Acesso
   ativo", como hoje). Quando não há e-mail → orienta cadastrar o e-mail primeiro
   (o link depende do e-mail da ficha).
3. O `base` da URL vem do request (esquema+host), para o link funcionar em local e
   em produção.

### Aluno: abrir o link e criar o acesso (público)
4. `GET /ativar/{token}` (PÚBLICO): valida o token (assinatura + expiração) e o aluno:
   - token inválido/expirado → página de erro neutra ("Link inválido ou expirado.
     Peça um novo ao seu treinador.").
   - aluno inexistente/arquivado → mesma página neutra.
   - aluno **já tem perfil** → "Seu acesso já foi criado" + link para `/login`.
   - ok → página "Crie seu acesso": mostra o **e-mail do aluno (readonly)** e campos
     **senha** + **confirmar senha**.
5. `POST /ativar/{token}` (PÚBLICO): revalida tudo (token + aluno + sem perfil);
   valida senha (mínimo 8 caracteres; senha == confirmação, senão re-renderiza com
   erro, sem vazar a senha). Então:
   - chama `supabase.signup(email_do_aluno, senha)`:
     - sucesso com sessão (confirmação de e-mail desligada no Supabase) → cria
       `Perfil(papel="aluno", aluno_id, user_id)` → abre a sessão do aluno →
       redireciona `/aluno`.
     - sucesso sem sessão (confirmação de e-mail ligada) → cria o `Perfil` mesmo
       assim (com o `user_id` retornado) → página "Conta criada! Confirme seu e-mail
       e depois entre em /login".
     - e-mail já registrado no Supabase → mensagem amigável ("Já existe uma conta com
       esse e-mail. Entre pelo login.") + link `/login`; não cria perfil duplicado.
     - Supabase não configurado / signups desativados / erro de rede → mensagem
       genérica ("Não foi possível criar o acesso agora."), nada é persistido.
6. Após ativado, o 1º (ou próximo) login do aluno cai em `/aluno` (o `Perfil` já
   existe; a Fase 3.1 cuida do roteamento).

### Geral
7. `/ativar` entra no allowlist do gate (público). Nenhum comportamento anterior
   muda; suíte segue verde. Sem migração/model novo (o `Perfil` já modela o vínculo;
   a existência dele = "ativado").

## Pré-condições
- Épico de login concluído (perfis, gate, /login, área do aluno). HEAD 0019.
- `itsdangerous` + `config.secret_key()` disponíveis (Fase 1).
- **Config do Supabase (PO):** "Allow new users to sign up" = ON (senão o signup via
  anon key é bloqueado). Recomendado "Confirm email" = OFF para ativação instantânea
  (o link do coach já é a verificação de que é o aluno certo); se ficar ON, o fluxo
  degrada para "confirme o e-mail e depois entre" (item 5).

## Arquivos a criar
- `kairos/auth/tokens.py` — `gerar_token_ativacao(aluno_id) -> str` e
  `ler_token_ativacao(token) -> Optional[int]` via `itsdangerous.URLSafeTimedSerializer`
  (secret = `config.secret_key()`, salt fixo p.ex. "ativacao-aluno"), com
  `MAX_AGE` (ex.: 7 dias) e retorno None em token ruim/expirado. Nunca levanta pro
  chamador (retorna None).
- `kairos/templates/auth/ativar.html` — página pública "Crie seu acesso" (layout
  autônomo no estilo do login: `#fundo3d`+scrim, wordmark, `.cad-card`; e-mail
  readonly + senha + confirmar; estados de erro/expirado/já-ativado/confirme-email).
- `tests/test_ativacao_aluno.py` — token (válido/expirado/adulterado→None), fluxo de
  ativação (mockando `supabase.signup`): happy path cria Perfil+sessão→/aluno; sem
  sessão (confirmação ligada)→cria Perfil+mensagem; já-ativado→manda pro login;
  token inválido→erro; senha curta/divergente→erro; e-mail já registrado→mensagem;
  e o link aparecendo na ficha do coach só quando elegível.

## Arquivos a modificar
- `kairos/auth/supabase.py` — nova `signup(email, senha) -> Dict[str,str]` chamando
  `POST {url}/auth/v1/signup` (header `apikey`), devolvendo
  `{user_id, email, access_token|""}`; distingue "e-mail já registrado" (levanta um
  `AuthEmailJaRegistrado` novo) de erro genérico (`AuthError`) e de não-configurado
  (`AuthNaoConfigurado`); nunca loga senha/token.
- `kairos/auth/routes.py` — `GET/POST /ativar/{token}` (públicos), reusando
  `service.get_perfil_by_aluno`, `alunos.service.get_aluno`, `tokens.*`,
  `supabase.signup`, `service.criar_perfil`, e abrindo a sessão do aluno no sucesso
  com sessão (mesmo shape da Fase 3.1: `{user_id,email,papel:"aluno",aluno_id}`).
- `kairos/auth/middleware.py` — `_is_public`: liberar `/ativar` (ex.:
  `path.startswith("/ativar")`).
- `kairos/alunos/routes.py` — na montagem do contexto da ficha (`GET /alunos/{id}`),
  quando `acesso_status == "aguardando"` (tem e-mail, sem perfil), incluir
  `link_ativacao = <base do request> + "/ativar/" + gerar_token_ativacao(id)` e a
  validade em dias; senão `link_ativacao = None`.
- `kairos/templates/alunos/ficha.html` — na seção "Acesso ao app", quando houver
  `link_ativacao`, mostrar o campo copiável + a instrução.

## Camadas envolvidas
- **integração** (`integracao-writer`): `auth/supabase.py::signup` (chamada HTTP,
  erros, sem logar segredo).
- **serviço** (`servico-writer`): `auth/tokens.py` (gerar/ler token assinado).
- **aplicação** (`aplicacao-writer`): rotas `/ativar` + allowlist do gate + o
  `link_ativacao` no contexto da ficha.
- **frontend** (`frontend-writer`): `auth/ativar.html` + o trecho do link na
  `ficha.html`.
- **testes** (`teste-writer`): `tests/test_ativacao_aluno.py` + suíte verde.

## Fora de escopo
- Reset de senha / "esqueci a senha" (Supabase faz; fatia futura).
- Reenviar/expirar/revogar link manualmente (por ora: validade por tempo; regenerar
  é só recarregar a ficha).
- Envio automático do link (o coach entrega; sem SMTP).
