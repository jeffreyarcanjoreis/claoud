# 33 — Esqueci minha senha (redefinição via Supabase)

Complemento do épico de login: fluxo de redefinição de senha para coach e alunos.

## Status
concluída

## Decisão do PO
Redefinição por e-mail (fluxo padrão do Supabase). O PO vai **ligar um provedor de
e-mail (Resend) no Supabase** — pré-requisito, ação no painel (ver "Pré-condições").

## Como funciona (fluxo)
1. No login, um link **"Esqueci minha senha"** leva a `/esqueci-senha`.
2. A pessoa informa o e-mail → o app chama o `recover` do Supabase → o **Supabase
   envia** um e-mail com um link de redefinição apontando para `/redefinir-senha`.
3. A pessoa clica no link do e-mail e cai em `/redefinir-senha`, onde o Supabase
   entrega um **token de recuperação no fragmento da URL** (`#access_token=...`).
4. A página lê esse token (JS mínimo → campo escondido), a pessoa digita a **senha
   nova** (+ confirmar), e o app atualiza a senha no Supabase com esse token.
5. Sucesso → volta pro `/login` com aviso "senha redefinida, entre com a nova senha".

## Especificação funcional
1. **Link no login:** `auth/login.html` ganha "Esqueci minha senha" → `/esqueci-senha`.
2. **`GET /esqueci-senha` (público):** formulário com um campo de e-mail.
3. **`POST /esqueci-senha` (público):** chama `supabase.recover(email, redirect_to)`
   (redirect_to = `{base do request}/redefinir-senha`). Resposta **sempre genérica**
   ("Se houver uma conta com esse e-mail, enviamos um link.") — nunca revela se o
   e-mail existe (anti-enumeração). Falha de rede/config → mensagem genérica de erro.
4. **`GET /redefinir-senha` (público):** página "Defina uma nova senha". Um JS mínimo
   lê `window.location.hash`, extrai `access_token` e `type=recovery`, e preenche um
   campo escondido; sem token no fragmento → estado "link inválido ou expirado".
   Campos: senha nova + confirmar.
5. **`POST /redefinir-senha` (público):** recebe `access_token` (do campo escondido),
   `senha`, `confirmar`. Valida (mín. 8; senha == confirmar; senão re-renderiza com
   erro, sem vazar a senha). Chama `supabase.atualizar_senha(access_token, senha)`
   (→ `PUT /auth/v1/user`, header `apikey` + `Authorization: Bearer <access_token>`,
   corpo `{password}`). Sucesso → 303 pro `/login` com flag de sucesso. Token
   inválido/expirado (401/403 do Supabase) → estado "link inválido/expirado, peça um
   novo". Nunca loga senha nem token.
6. **Gate:** `/esqueci-senha` e `/redefinir-senha` entram no allowlist público
   (`_is_public`), como `/ativar`.
7. **Segurança/idioma:** senha só trafega form→servidor→Supabase por HTTPS, nunca
   gravada/logada (mesmo padrão de login/signup/ativação). Textos pt-BR (regra 10).
8. Nenhum comportamento anterior muda; suíte segue verde. Sem migração/model.

## Pré-condições (ação do PO no painel — guiado; o código não depende disso pra ser
escrito, só pra o envio real funcionar)
- **Provedor de e-mail (Resend) ligado no Supabase** (Authentication → Emails/SMTP →
  Custom SMTP), senão o e-mail de redefinição não sai de forma confiável.
- **Redirect URL** liberada no Supabase (Authentication → URL Configuration →
  Redirect URLs): incluir `http://localhost:8000/redefinir-senha` (e, quando houver
  hospedagem, a URL de produção).

## Arquivos a criar
- `kairos/templates/auth/esqueci_senha.html` — página pública (layout autônomo no
  estilo do login: `#fundo3d`+scrim, wordmark, `.cad-card`), form de e-mail +
  estados (inicial / "enviado" genérico / erro genérico).
- `kairos/templates/auth/redefinir_senha.html` — página pública com o JS mínimo que
  lê o `access_token` do fragmento pra um campo escondido; form senha+confirmar;
  estados (ok / sem-token-"link inválido" / erro de validação / expirado).
- `tests/test_reset_senha.py` — cobre: link no login; `/esqueci-senha` GET/POST
  (resposta genérica; `recover` chamado com o e-mail; anti-enumeração); parsing do
  `supabase.recover`/`atualizar_senha` (mockando urllib, como
  `tests/test_supabase_signup.py`): sucesso, token inválido→erro, validação de senha
  (curta/divergente → sem chamar o Supabase), gate público das duas rotas.

## Arquivos a modificar
- `kairos/auth/supabase.py` — duas funções novas no estilo de `login`/`signup`
  (urllib, nunca logar senha/token/apikey):
  - `recover(email, redirect_to) -> None`: `POST {url}/auth/v1/recover?redirect_to=…`
    com header `apikey` e corpo `{email}`; erros viram `AuthError`
    genérico / `AuthNaoConfigurado`. Não distingue e-mail inexistente (anti-enum).
  - `atualizar_senha(access_token, senha) -> None`: `PUT {url}/auth/v1/user` com
    `apikey` + `Authorization: Bearer <access_token>` e corpo `{password}`; 401/403
    → `AuthTokenInvalido` (nova exceção) para a página mostrar "link expirado"; outros
    → `AuthError` genérico.
- `kairos/auth/routes.py` — rotas `GET/POST /esqueci-senha` e
  `GET/POST /redefinir-senha` (públicas), finas, delegando ao `supabase`.
- `kairos/auth/middleware.py` — `_is_public`: liberar `/esqueci-senha` e
  `/redefinir-senha`.
- `kairos/templates/auth/login.html` — link "Esqueci minha senha" + exibir o aviso
  de sucesso quando vier do reset (ex.: `?redefinida=1`).

## Camadas envolvidas
- **integração** (`integracao-writer`): `recover` + `atualizar_senha` em
  `auth/supabase.py`.
- **aplicação** (`aplicacao-writer`): as 4 rotas + allowlist do gate.
- **frontend** (`frontend-writer`): `esqueci_senha.html`, `redefinir_senha.html`
  (com o JS mínimo do fragmento) + link/aviso no `login.html`.
- **testes** (`teste-writer`): `tests/test_reset_senha.py` + suíte verde.

## Fora de escopo
- Troca de senha por dentro da área logada (aluno/coach já autenticado) — fatia
  futura, se quiser.
- 2FA / verificação por SMS.
