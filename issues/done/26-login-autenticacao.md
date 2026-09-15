# Épico — Autenticação com Supabase Auth (coach + área de alunos)

## Status
CONCLUÍDO (todas as fases). Fase 1 (login do coach + gate + perfis, migr. 0018),
Fase 2.1 (e-mail do aluno + auto-vínculo no 1º login, migr. 0019 — issue 29),
Fase 3.1 (gate multiusuário + o aluno entra em /aluno — issue 30) e Fase 3.2
(área do aluno com o próprio conteúdo, isolado, read-only — issue 31) construídas e
testadas. Suíte 670 verde. **ATIVAÇÃO do fluxo do aluno pendente do PO:** aplicar a
migração 0019 no Supabase + criar o usuário do aluno no Supabase (Authentication →
Users) com o MESMO e-mail cadastrado na ficha → no 1º login o app vincula e libera a
área. (As chaves de login do coach já foram ativadas.)

## Decisão do PO
- **Supabase Auth** (GoTrue) como base de autenticação (não login nativo).
- Já planejando **login de alunos**, não só o coach → multiusuário com papéis.

## Por que isso é um épico (e não uma fatia)
Supabase Auth num app **server-rendered** (Jinja, não SPA) tem mais partes móveis, e
"área de alunos" adiciona papéis + isolamento de dados + uma UI nova. Complexidades
reais a tratar:
- **Verificar o token no backend**: o login chama a API do Supabase Auth
  (`/auth/v1/token?grant_type=password`) e recebe um JWT (access) + refresh token. O
  backend precisa **validar o JWT** a cada request (assinatura + expiração) — via a
  chave pública (JWKS) do projeto ou o JWT secret. Precisa de uma lib de JWT (PyJWT)
  ou validar chamando `/auth/v1/user` (mais lento). Refresh do token quando expira.
- **Sessão server-side**: guardar os tokens num cookie seguro (HttpOnly, assinado),
  já que não é SPA com localStorage.
- **Papéis (coach vs aluno)** e **vínculo**: uma tabela `perfis` ligando o
  `auth.users.id` (Supabase) ao papel e, para alunos, ao `Aluno` correspondente.
- **Isolamento de dados**: um aluno só pode ver o PRÓPRIO acompanhamento/treinos/
  avaliações — nunca de outro. Isso muda as consultas e as rotas.
- **UI do aluno**: uma área nova, separada do painel do coach.
- **Config/segredos**: URL do projeto, `anon key`, e o segredo de verificação do JWT
  no `.env`. Testar cria usuários reais no Auth do Supabase.

## Roadmap proposto (em fases, uma de cada vez, com /plan→aprovação por fase)

### FASE 1 — Fundação de auth + login do COACH (esta issue, quando aprovada)
**Abordagem simplificada (decidida):** o Supabase Auth só **confere a senha no
login**; depois o app mantém a **própria sessão assinada** (cookie). Assim NÃO
precisamos verificar JWT a cada request nem do *JWT secret* — só do Project URL +
anon key + um `KAIROS_SECRET_KEY` (para assinar a sessão; eu gero um).
- Config: `supabase_url()`, `supabase_anon_key()`, `secret_key()` — no `.env`.
- Integração isolada `kairos/auth/supabase.py`: `login(email, senha)` chama
  `POST {url}/auth/v1/token?grant_type=password` (urllib, header `apikey`), devolve
  `{user_id, email}` no sucesso, levanta `AuthError` em credencial inválida e
  `AuthNaoConfigurado` quando faltam URL/anon key. Sem lib de JWT.
- `SessionMiddleware` + gate por path (público: `/vitrine`, `/comecar`, `/login`,
  `/logout`, `/static`, `/health`, `/favicon`; resto exige sessão de **coach**).
- Rotas `GET/POST /login`, `POST /logout`; "Entrar" da vitrine → `/login`; "Sair" no
  painel. Tela `auth/login.html` (visual da marca).
- Tabela `perfis` (migração 0018): `user_id` (uuid do Supabase, texto, unique),
  `papel` (coach|aluno), `aluno_id` opcional (FK), `created_at`.
- **Bootstrap:** se ainda não existe nenhum perfil de coach, o **primeiro login
  bem-sucedido vira coach** (cria a linha em `perfis`). Seguro porque só quem tem a
  credencial do Supabase consegue logar. (CLI `definir-perfil <user_id> <papel>`
  fica como utilitário, mas não é obrigatório pro Phase 1.)
- Testes: gate redireciona sem sessão; público aberto; login/logout; verificação de
  token; suíte segue verde (conftest autentica os testes atuais como coach; testes de
  auth com `@pytest.mark.real_auth`).

### FASE 2 — Papéis + vínculo aluno↔usuário
- Ligar cada aluno a um usuário do Supabase (convite/criação), papel=aluno em
  `perfis.aluno_id`. Coach cria/convida o acesso do aluno pela ficha.

### FASE 3 — Área do aluno (dados só dele)
- UI própria do aluno: vê o próprio acompanhamento, treinos, avaliações, próximos
  agendamentos. Isolamento de dados garantido nas consultas e nas rotas.
- (Opcional) reset de senha por e-mail (Supabase faz), 2FA.

## O que preciso de você pra começar a Fase 1
Do painel do Supabase → **Settings → API** e **Authentication**:
1. **Project URL** (ex.: `https://<ref>.supabase.co`).
2. **anon public key** (a chave `anon`/`public`).
3. Como o projeto assina o JWT: o **JWT Secret** (Settings → API → JWT Settings) OU
   confirmar que usa chaves assimétricas (aí uso o **JWKS** em `/auth/v1/.well-known/jwks.json`).
4. Ativar **Email/Password** em Authentication → Providers (provavelmente já está).
5. Criar o SEU usuário coach (Authentication → Users → Add user, com seu e-mail e uma
   senha que só você define). Depois eu ligo esse usuário como papel=coach.
Esses valores vão pro `.env` (git-ignored). O `anon key` é público por natureza; o
JWT secret é sensível — fica só no `.env`.

## Fora de escopo desta issue (Fase 1)
- Fases 2 e 3 (alunos) — épicos próprios depois.
- Gestão de múltiplos coaches pela UI.

## Camadas / subagentes (Fase 1)
configuracao-writer (config supabase/jwt) → banco-migracao-writer (perfis + 0018) →
integracao-writer (kairos/auth/supabase.py — chamadas HTTP + verificação JWT) →
aplicacao-writer (middleware + rotas login/logout + SessionMiddleware) → cli-writer
(definir-perfil) → frontend-writer (login.html + Sair) → teste-writer (suíte + gate).
