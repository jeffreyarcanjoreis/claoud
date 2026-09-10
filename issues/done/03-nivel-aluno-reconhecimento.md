# Aluno se reconhece no nível (área do aluno)

## Descrição
Na sua área, o aluno vê a sua frente e o que ela significa (ou "sem registro" + convite a falar com o coach, sem inventar), vê os quatro níveis descritos em 1ª pessoa e se reconhece em um deles, com nota opcional. Reconhecer-se grava o reconhecimento com a data e passa a mostrá-lo como "onde me reconheço hoje"; pode rever quando quiser. O aluno vê o histórico dos próprios reconhecimentos (mais recente primeiro). Isolamento: só o próprio (aluno_id da sessão).

## Depende de
01 (frente — para exibir frente + significado), 02 (dados + serviço do nível)

## Status
concluída

## Especificação funcional
Lado do aluno, espelhando `kairos/registro_treino/routes.py` + `templates/area_aluno/registro.html`: rotas finas, `aluno_id` **sempre da sessão** (`current_user(request).get("aluno_id")`, nunca da URL), toda regra no serviço. Texto em 1ª pessoa (regras 11–14). Uma nova aba **"Nível"** na navegação do aluno leva a `/aluno/nivel`.

- **`GET /aluno/nivel`** → página "Meu nível":
  - **Frente (leitura):** usa `get_aluno(aluno_id)` (já traz `frente_label`/`frente_significado`, da issue 01). Se há frente → mostra o label + o significado. Se não → `<span class="none">sem registro</span>` + um convite curto ("Converse com seu coach para definir sua frente."). Nunca inventa (regra 6).
  - **Reconhecimento:** os quatro níveis (`NIVEL_OPCOES`) com `NIVEL_LABELS` + `NIVEL_DESCRICOES` (1ª pessoa), o **atual** (`nivel_atual(aluno_id)`) marcado como "onde me reconheço hoje"; campo de nota opcional.
  - **Histórico:** `list_reconhecimentos(aluno_id)` (data, nível, nota), mais recente primeiro; vazio → mensagem "Você ainda não se reconheceu num nível.".
- **`POST /aluno/nivel`** (form `nivel`, `nota`): `reconhecer(aluno_id, nivel=nivel, nota=nota)`; sucesso → `RedirectResponse` 303 para `/aluno/nivel`; `ValidationError` → re-render 400 com a mensagem, sem perder o digitado.
- **Isolamento:** todo acesso é do aluno da sessão; nunca de outro. Se a sessão não resolve um `aluno_id`, a página se comporta como "sem dados" (frente "sem registro", histórico vazio) — igual ao padrão tolerante do `area_aluno`.

Casos de borda: nível inválido (não deveria vir do form, mas) → 400 sem gravar; nota vazia → NULL; reconhecer o mesmo nível de novo grava outro registro no histórico (evolução); sem frente definida → o aluno ainda pode se reconhecer (os quatro níveis são os mesmos em qualquer frente), só não vê o rótulo da frente.

## Pré-condições
- Issue 01 concluída (`get_aluno` traz `frente_label`/`frente_significado`). Issue 02 concluída (`kairos.nivel.service`: `NIVEL_OPCOES`, `NIVEL_LABELS`, `NIVEL_DESCRICOES`, `ValidationError`, `reconhecer`, `nivel_atual`, `list_reconhecimentos`). Área do aluno + auth gate existem. HEAD de migração: 0024.

## Arquivos a criar
- `kairos/nivel/routes.py` — `router = APIRouter()`; `GET /aluno/nivel` e `POST /aluno/nivel` (lado do aluno). Importa `current_user` (`kairos.auth.middleware`), `get_aluno` (`kairos.alunos.service`), `reconhecer`/`nivel_atual`/`list_reconhecimentos`/`NIVEL_OPCOES`/`NIVEL_LABELS`/`NIVEL_DESCRICOES`/`ValidationError` (`kairos.nivel.service`), `templates` (`kairos.web`). Helpers de display (opções `(valor,label,descricao)`, formatar reconhecimento com data `%d/%m/%Y`).
- `kairos/templates/area_aluno/nivel.html` — estende `area_aluno/base.html`: seção Frente (label+significado ou "sem registro"+convite), formulário de reconhecimento (os 4 níveis como opções selecionáveis em 1ª pessoa, o atual destacado, nota opcional, botão), e o histórico. Reusa classes existentes (`cad-card`, `aluno-secao`, `checkin-form`/`field`, `aluno-lista-item`, `aluno-vazio`, `message-error`).

## Arquivos a modificar
- `kairos/main.py` — importar `from kairos.nivel.routes import router as nivel_router` e `app.include_router(nivel_router)` (junto dos outros).
- `kairos/templates/area_aluno/base.html` — item **"Nível"** na `nav.aluno-nav` (ex.: logo após "Treinos"): `href="/aluno/nivel"`, ativo quando `p.startswith('/aluno/nivel')`.

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): `kairos/nivel/routes.py` (GET/POST do aluno) + include no `main.py`.
- **frontend** (`frontend-writer`): `templates/area_aluno/nivel.html` + item na nav do aluno (`base.html`).
- **testes** (`teste-writer`): `tests/test_nivel_aluno.py` — GET 200 (mostra frente e os níveis; "sem registro" quando sem frente), POST válido → 303 e persiste (via `list_reconhecimentos`), POST reconhecendo de novo → histórico cresce, "onde me reconheço hoje" reflete o atual, isolamento (grava sempre no aluno da sessão). Helper `_login_as_aluno` deve dar patch em `kairos.nivel.routes.current_user` também (além de auth.middleware e area_aluno.routes), como no test_checkin/test_registro. Suíte anterior verde.
