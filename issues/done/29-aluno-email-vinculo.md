# 29 — E-mail do aluno + auto-vínculo no 1º login (Fase 2 do épico de login)

Fatia 2.1 do épico [26-login-autenticacao.md](26-login-autenticacao.md).

## Status
concluída

## Contexto / decisão do PO
Modo de acesso do aluno escolhido: **vínculo por e-mail no 1º login**. O coach cria
o usuário do aluno no painel do Supabase (e-mail + senha inicial que ele repassa ao
aluno). No 1º login bem-sucedido, o app **liga automaticamente** esse usuário à ficha
cujo e-mail bate, criando um `Perfil` com `papel="aluno"` e `aluno_id`. Sem segredo
novo, sem SMTP. Esta fatia só cria o **vínculo**; a área do aluno (deixar o aluno
entrar de fato) é a Fase 3 — aqui o aluno ainda vê "acesso não liberado" ao logar.

## Especificação funcional

### Campo e-mail na ficha do aluno
1. `alunos` ganha uma coluna `email` (texto, opcional/nullable). Sem dado → NULL na
   base e "sem registro" na tela (regra 6). Não é única (dois alunos podem, em tese,
   compartilhar; a ambiguidade é tratada no login, ver item 6).
2. O e-mail é **normalizado em minúsculas** ao gravar (create e update), para o
   casamento no login ser determinístico. String vazia/espaços → NULL.
3. O formulário de criar/editar aluno mostra um campo "E-mail" (type=email). Salvar
   grava; editar troca; apagar o campo → NULL.

### Conversão lead → aluno
4. Ao "Transformar em aluno", o e-mail é derivado do `contato` da lead **apenas
   quando parece um e-mail** (contém "@" e não contém espaço); caso contrário `email`
   fica NULL (regra 6 — não inventar e-mail a partir de um telefone). O campo
   `contact` do aluno continua recebendo o `contato` da lead como hoje (sem mudança).

### Auto-vínculo no login
5. `resolver_papel_no_login(user_id, email)` passa a receber também o **e-mail** (que
   já volta de `supabase.login`). Ordem de decisão:
   1. Se já existe `Perfil` para o `user_id` → devolve o `papel` (inalterado).
   2. Senão, se ainda não existe nenhum coach → **bootstrap**: cria perfil coach e
      devolve "coach" (inalterado).
   3. Senão, tenta o **vínculo por e-mail**: procura alunos **ativos** cujo `email`
      (case-insensitive) seja igual ao e-mail do login e que **ainda não tenham
      perfil**. Se houver **exatamente um** → cria `Perfil(papel="aluno",
      aluno_id=<esse aluno>)` e devolve "aluno". Se houver **zero ou mais de um** →
      devolve `None` (sem acesso; nada é criado).
6. Guardas de segurança (casos de borda):
   - **E-mail repetido** em 2+ alunos ativos → ambíguo → `None`, nenhum perfil criado
     (evita acesso cruzado à ficha errada).
   - Aluno cujo e-mail bate mas **já tem perfil** → não é religado; não cria segundo
     perfil (idempotente em logins repetidos).
   - Aluno **inativo/arquivado** com e-mail igual → não vincula (só alunos ativos).
   - E-mail nulo/vazio no lado do aluno nunca casa com nada.
7. A rota `POST /login` continua abrindo sessão **só para coach** nesta fatia; um
   aluno recém-vinculado (papel="aluno") ainda recebe a mensagem "Este acesso ainda
   não está liberado." (403). O vínculo foi criado; a entrada vem na Fase 3.

### Selo de status de acesso na ficha (visão do coach)
8. A ficha do aluno mostra o e-mail e um **selo de status de acesso**, derivado assim:
   - `email` é NULL → "Sem e-mail" (neutro).
   - existe `Perfil` com `aluno_id` deste aluno → "Acesso ativo" (positivo).
   - `email` presente e sem perfil → "Aguardando 1º login" (atenção).

### Geral
9. Os testes anteriores seguem verdes; nenhum comportamento anterior muda (o
   bootstrap do coach e o gate continuam idênticos). A assinatura nova de
   `resolver_papel_no_login` é atualizada em seu único chamador (`auth/routes.py`).

## Pré-condições
- Épico 26 Fase 1 construída (tabela `perfis`, `auth/*`, gate, login) — OK.
- Cabeça de migração atual: `0018_create_perfis`.

## Arquivos a criar
- `migrations/versions/0019_add_email_to_alunos.py` — adiciona a coluna `email`
  (`String(200)`, nullable) em `alunos`; `down_revision = "0018"`. `downgrade`
  remove a coluna. Tipo portável (regra 4).
- `tests/test_vinculo_aluno.py` — cobre itens 1–8: coluna/normalização; conversão
  lead→aluno (com "@" liga, sem "@" fica NULL); resolver nos casos 5/6 (match único,
  zero, ambíguo, já-com-perfil, inativo, case-insensitive; bootstrap e perfil
  existente inalterados); selo de status na ficha. Usa `@pytest.mark.real_auth` só
  onde exercitar a rota de login; os testes do resolver chamam o serviço direto (sem
  rede).

## Arquivos a modificar
- `kairos/alunos/models.py` — adiciona `email: Mapped[Optional[str]] =
  mapped_column(String(200), nullable=True)`.
- `kairos/alunos/service.py`:
  - `_to_dict` inclui `"email"`.
  - `_clean_fields`, `create_aluno`, `update_aluno` recebem `email` (normalizado com
    um `_normalize_email` que faz strip + `.lower()`, vazio → None).
  - nova `find_alunos_by_email(email) -> List[dict]`: alunos **ativos** com
    `lower(email) == lower(email_arg)` (lista, para detectar ambiguidade); e-mail
    vazio → `[]`, sem consultar.
- `kairos/auth/service.py`:
  - nova `get_perfil_by_aluno(aluno_id) -> Optional[dict]` (usada pelo resolver e
    pelo selo da ficha).
  - `resolver_papel_no_login(user_id, email)` — nova assinatura + lógica de vínculo
    do item 5/6 (import **local** de `find_alunos_by_email` dentro da função, como
    `contatos.service` faz com `alunos`, para não criar ciclo de import).
- `kairos/auth/routes.py` — `POST /login` passa `res["email"]` para
  `resolver_papel_no_login`.
- `kairos/contatos/service.py::converter_contato_em_aluno` — deriva `email` do
  `contato` (só quando "@" e sem espaço) e passa a `create_aluno`.
- `kairos/alunos/routes.py` — `create_aluno_route` e `update_aluno_route` ganham o
  `email: Optional[str] = Form(None)`, repassam ao serviço e incluem `email` no dict
  de valores no re-render de erro; a rota `GET /alunos/{id}` calcula o status de
  acesso via `auth.service.get_perfil_by_aluno` e injeta `email_display` +
  `acesso_status`/`acesso_label` no contexto.
- `kairos/templates/alunos/_form.html` — campo "E-mail" (type=email, name="email",
  value de `values.email`).
- `kairos/templates/alunos/ficha.html` — exibe e-mail + selo de status de acesso.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): coluna `email` + migração 0019.
- **serviço** (`servico-writer`): alunos (`email`, `find_alunos_by_email`), auth
  (`get_perfil_by_aluno`, `resolver_papel_no_login`), contatos (derivação do e-mail).
- **aplicação** (`aplicacao-writer`): rotas de aluno (form `email` + status) e a
  chamada atualizada em `auth/routes.py`.
- **frontend** (`frontend-writer`): `_form.html` + `ficha.html`.
- **testes** (`teste-writer`): `tests/test_vinculo_aluno.py` + suíte verde.
