# 30 — Gate multiusuário + landing do aluno (Fase 3.1 do épico de login)

Fatia 3.1 do épico [26-login-autenticacao.md](26-login-autenticacao.md). Depende de:
[29-aluno-email-vinculo.md](done/29-aluno-email-vinculo.md) (concluída — já cria o
`Perfil` papel="aluno" com `aluno_id` no 1º login).

## Status
concluída

## Contexto
Na Fatia 2.1 o aluno já ganha um `Perfil` no 1º login, mas ainda vê "acesso não
liberado" — o gate só deixa **coach** passar e o login só abre sessão de coach. Esta
fatia **deixa o aluno entrar**: cria a área própria dele (`/aluno`), com isolamento
de acesso (aluno não vê o painel do coach; coach não cai na área do aluno). O
**conteúdo** da área (treinos, agenda, avaliações do próprio aluno) é a Fatia 3.2 —
aqui é só a porta + a landing.

## Especificação funcional

### Gate multiusuário (por área)
1. Rotas **públicas** seguem iguais (`/login`, `/logout`, `/vitrine`, `/comecar`,
   `/static`, `/health`, `/favicon.ico`).
2. A **área do aluno** vive sob o prefixo `/aluno` — definido como
   `path == "/aluno"` ou `path.startswith("/aluno/")`. (Cuidado: `/alunos` — a lista
   do coach — NÃO casa com isso, pois é `/aluno` + `s`, não `/aluno/`.)
3. Papel exigido por área: rota da área do aluno → exige sessão **papel="aluno"**;
   qualquer outra rota não-pública (o painel inteiro) → exige **papel="coach"**
   (comportamento atual do coach inalterado).
4. Requisição sem sessão a uma rota protegida → redireciona a `/login?next=<path>`
   (como hoje).
5. Requisição **com sessão do papel errado** para a área → não faz loop: redireciona
   para a **casa do próprio papel** (coach → `/`; aluno → `/aluno`). Ex.: aluno
   logado que tenta `/alunos` ou `/financeiro` vai para `/aluno`; coach logado que
   tenta `/aluno` vai para `/`.

### Login por papel
6. `POST /login`: além do coach (inalterado), quando `resolver_papel_no_login`
   devolve **"aluno"**, abre a sessão com `{user_id, email, papel:"aluno",
   aluno_id:<do perfil>}` (o `aluno_id` vem de `service.get_perfil(user_id)`) e
   redireciona para `/aluno` (303). Se o `next` recebido for um caminho seguro sob
   `/aluno`, honra o `next`; senão vai para `/aluno`.
7. `GET /login` com sessão já ativa: coach → bounce para `/`; **aluno → bounce para
   `/aluno`** (hoje só trata coach).
8. A mensagem "Este acesso ainda não está liberado." (403 para papel != coach)
   deixa de acontecer para alunos vinculados — eles agora entram. Continua valendo
   para quem loga sem perfil/None (sem acesso).

### Landing do aluno
9. `GET /aluno`: página própria do aluno (layout autônomo, NÃO o shell do coach),
   com saudação "Olá, {primeiro nome do aluno}" — o nome vem de
   `alunos.service.get_aluno(<aluno_id da sessão>)`. Mostra um cartão de boas-vindas
   e um botão **Sair** (`POST /logout`, que já existe). Uma nota honesta de que os
   próprios treinos/agenda/avaliações chegam em breve (Fatia 3.2) — sem inventar
   dado (regra 6). Se o `aluno_id` da sessão não resolver um aluno (arquivado/
   removido), a saudação cai para um texto genérico, sem quebrar.
10. Visual alinhado ao login/cadastro (wordmark "Kairos", fundo 3D ambiente + scrim,
    cartão translúcido por cima) para a área do aluno parecer parte do app.

### Copy
11. A tela de login diz hoje "Acesse o painel do coach." — trocar para algo
    **neutro de papel** ("Acesse a sua conta.") já que o mesmo login serve coach e
    aluno.

### Geral
12. Nenhum comportamento do coach muda; os testes anteriores seguem verdes. Sem
    migração, sem model novo (usa `get_aluno`/`get_perfil` já existentes).

## Pré-condições
- Fatia 2.1 concluída (perfil de aluno nasce no 1º login). HEAD de migração: 0019.
- `SessionMiddleware` + `AuthGateMiddleware` já montados (Fase 1).

## Arquivos a criar
- `kairos/area_aluno/__init__.py` — pacote do novo comportamento (área do aluno).
- `kairos/area_aluno/routes.py` — `router` com `GET /aluno` (rota fina: lê
  `aluno_id` da sessão via `current_user`, busca `get_aluno`, renderiza a landing).
- `kairos/templates/area_aluno/inicio.html` — landing autônoma (wordmark, fundo 3D +
  scrim, cartão de saudação, botão Sair, nota "em breve"). Estáticos com
  `?v={{ asset_ver }}`.
- `kairos/static/css/area_aluno.css` — poucos estilos próprios da landing (reusa
  tokens/base; pode reaproveitar classes de `cadastro.css` se couber). Só se
  necessário; senão reusar `cadastro.css`.
- `tests/test_area_aluno.py` — cobre itens 1–11.

## Arquivos a modificar
- `kairos/auth/middleware.py`:
  - novo helper `_is_area_aluno(path)` (`path == "/aluno" or
    path.startswith("/aluno/")`).
  - `AuthGateMiddleware.dispatch`: determina o papel exigido pela área, e aplica as
    regras 3–5 (sem sessão → `/login?next=`; papel errado → casa do próprio papel).
    Extrair um helper `_home_do_papel(papel)` (`"aluno"` → `/aluno`, senão `/`).
- `kairos/auth/routes.py`:
  - `login_submit`: ramo para `papel == "aluno"` (abre sessão com `aluno_id` de
    `service.get_perfil(res["user_id"])`, redireciona a `/aluno` ou `next` seguro sob
    `/aluno`); helper `_safe_next_aluno` OU generalizar `_safe_next` com um prefixo
    permitido. Coach inalterado.
  - `login_form`: bounce do aluno logado para `/aluno`.
- `kairos/main.py` — importar e `include_router` do `area_aluno.routes`.
- `kairos/templates/auth/login.html` — trocar o subtítulo para "Acesse a sua conta."

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): gate (`middleware.py`), login por papel
  (`auth/routes.py`), rota `GET /aluno` (`area_aluno/routes.py`), include no
  `main.py`.
- **frontend** (`frontend-writer`): `area_aluno/inicio.html` (+ css se preciso) e o
  ajuste de copy no `login.html`.
- **testes** (`teste-writer`): `tests/test_area_aluno.py` + suíte verde. (Atenção: o
  `conftest` autologa todos os testes como **coach** via patch de `current_user`; os
  testes da área do aluno devem sobrescrever esse patch para um dict de aluno
  `{user_id, email, papel:"aluno", aluno_id}` ou usar `@pytest.mark.real_auth` com
  sessão de aluno.)

## Fora de escopo (fica para a Fatia 3.2)
- Conteúdo real da área do aluno (próximos agendamentos, treinos atribuídos,
  avaliações/acompanhamento) com isolamento por `aluno_id` nas consultas.
- Aluno editar qualquer coisa (a área nasce só-leitura).
