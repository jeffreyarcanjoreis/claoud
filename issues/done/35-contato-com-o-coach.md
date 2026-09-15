# 35 — Contato com o coach (Fase 1 do roadmap da área do aluno)

Fase 1 de [docs/roadmap-area-aluno.md](../docs/roadmap-area-aluno.md). A primeira
**válvula**: um canal de mensagens aluno ↔ coach. É a primeira **escrita** na área do
aluno (intencional — a spec diz "todo input do aluno tem que mudar algo visível").

## Status
concluída

## Decisão de escopo
- Só **texto** nesta fatia (áudio fica pra depois).
- Uma conversa **por aluno** (coach ↔ aquele aluno). Sem grupos.
- O aluno escreve na área dele; o coach lê e responde **na ficha do aluno**; cada lado
  vê o "novo" do outro.

## Modelo de "lido"
Uma mensagem tem `lida` = **o destinatário já leu**. O destinatário é sempre o *outro*
lado: mensagem do coach → destinatário é o aluno; mensagem do aluno → destinatário é o
coach. Marcar como lida acontece ao **abrir a conversa** (GET), nunca ao enviar.

## Especificação funcional

### Modelo + migração
1. Tabela `mensagens` (migração **0020**): `id`, `aluno_id` (FK alunos.id), `autor`
   ("coach" | "aluno"), `texto` (Text, obrigatório), `lida` (Boolean, default False),
   `created_at`. Tipos portáveis (regra 4).

### Serviço (`kairos/mensagens/service.py`)
2. `enviar_mensagem(aluno_id, autor, texto)` — valida `autor` ∈ {coach, aluno} e
   `texto` não-vazio (senão `ValidationError` pt-BR); grava `lida=False`; loga.
3. `listar_conversa(aluno_id)` — todas as mensagens do aluno em ordem cronológica
   (asc), como dicts (autor, texto, created_at). Read-only.
4. `marcar_lidas(aluno_id, por)` — marca como lidas as mensagens **destinadas a
   `por`**: `por="aluno"` → mensagens `autor="coach"` não lidas viram lidas;
   `por="coach"` → mensagens `autor="aluno"` não lidas viram lidas. Loga.
5. `contar_nao_lidas(aluno_id, para)` — quantas não lidas destinadas a `para`
   (para o selo "novo"). Read-only.
6. `ultima_do_coach(aluno_id)` — a última mensagem do coach (pro card "Recado do
   coach" no home), ou None. Read-only.
7. `alunos_com_nao_lidas()` — set/mapa de `aluno_id → nº de mensagens do aluno não
   lidas`, pro coach saber quem escreveu (badge na lista de alunos). Read-only.

### Lado do aluno
8. Nova sub-página **Contato** na navegação do aluno → `GET /aluno/mensagens`: mostra
   a conversa (`listar_conversa` do `aluno_id` da **sessão**) + um formulário de envio;
   ao abrir, `marcar_lidas(aluno_id, "aluno")`. Estado vazio honesto ("Nenhuma
   mensagem ainda. Escreva pro seu treinador.").
9. `POST /aluno/mensagens` (Form: `texto`) → `enviar_mensagem(aluno_id da sessão,
   "aluno", texto)` → redireciona de volta pra `/aluno/mensagens` (303). Texto vazio →
   re-renderiza com erro, sem gravar. **É a 1ª rota de escrita da área do aluno** —
   segue gated (só aluno) e usa sempre o `aluno_id` da sessão.
10. No **home** (`/aluno`), um card **"Recado do coach"**: se houver `ultima_do_coach`,
    mostra um trecho + selo **"novo"** quando `contar_nao_lidas(aluno_id,"aluno") > 0`,
    linkando pra `/aluno/mensagens`. Sem mensagem → não aparece (ou nota discreta).

### Lado do coach
11. Nova sub-aba **Mensagens** na ficha do aluno (`ficha_layout.html`) →
    `GET /alunos/{id}/mensagens`: mostra a conversa daquele aluno + formulário de
    resposta; ao abrir, `marcar_lidas(id, "coach")`. 404 se o aluno não existe.
12. `POST /alunos/{id}/mensagens` (Form: `texto`) → `enviar_mensagem(id, "coach",
    texto)` → redireciona pra a sub-aba (303). Texto vazio → re-render com erro.
13. Na **lista de alunos** (`GET /alunos`), um selo/contador nos alunos que têm
    mensagens não lidas do aluno (via `alunos_com_nao_lidas`) — o "inbox" leve do
    coach.

### Geral
14. Isolamento: o aluno só acessa a **própria** conversa (aluno_id da sessão, nunca da
    URL); o coach acessa por aluno_id na URL (ele gere todos — correto). Textos pt-BR
    (regra 10); toda escrita loga (regra 8). Suíte anterior segue verde.

## Pré-condições
- Área do aluno com nav (Fase 0, issue 34) e gate por papel (Fases 3.1/3.2). HEAD 0019.

## Arquivos a criar
- `kairos/mensagens/__init__.py`, `kairos/mensagens/models.py` (Mensagem),
  `kairos/mensagens/service.py`, `kairos/mensagens/routes.py` (as 4 rotas: aluno
  GET/POST + coach GET/POST).
- `migrations/versions/0020_create_mensagens.py`.
- `kairos/templates/area_aluno/mensagens.html` (conversa + envio, estende
  `area_aluno/base.html`).
- `kairos/templates/mensagens/ficha_mensagens.html` (conversa + resposta, estende
  `alunos/ficha_layout.html`).
- `tests/test_mensagens.py` (serviço + rotas dos dois lados + isolamento + "lido").

## Arquivos a modificar
- `kairos/main.py` — incluir o `mensagens.routes` router.
- `kairos/templates/area_aluno/base.html` — item **Contato** na nav do aluno.
- `kairos/area_aluno/routes.py` — `GET /aluno` injeta o card "Recado do coach"
  (última do coach + nº não lidas).
- `kairos/templates/area_aluno/inicio.html` — o card "Recado do coach".
- `kairos/templates/alunos/ficha_layout.html` — sub-aba **Mensagens**.
- `kairos/alunos/routes.py` (`GET /alunos`) + `kairos/templates/alunos/lista.html` —
  selo de mensagens não lidas por aluno.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): modelo `Mensagem` + migração 0020.
- **serviço** (`servico-writer`): `mensagens/service.py`.
- **aplicação** (`aplicacao-writer`): `mensagens/routes.py` (4 rotas), o card no home
  do aluno, o badge na lista de alunos, include no `main.py`.
- **frontend** (`frontend-writer`): `mensagens.html` (aluno) + `ficha_mensagens.html`
  (coach) + nav "Contato" + card "Recado do coach" + sub-aba na ficha + selo na lista.
- **testes** (`teste-writer`): `tests/test_mensagens.py` + suíte verde.

## Fora de escopo (fases/futuro)
- Áudio; anexos; notificações push/e-mail de nova mensagem; caixa de entrada unificada
  do coach (por ora, badge na lista + sub-aba por aluno); moderação.
