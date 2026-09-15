# Sub-aba Avaliações com a lista real

## Descrição
Comportamentos 1, 2, 3: a sub-aba "Avaliações" da ficha deixa de mostrar "em breve" (o marcador some da sub-nav) e passa a listar as avaliações do aluno em ordem cronológica inversa; quando não há nenhuma, mostra um estado vazio com botão para registar a primeira.

## Depende de
02-avaliacao-servico

## Especificação funcional
- `GET /alunos/{id}/avaliacoes` deixa de mostrar o `.coming-soon` e passa a listar as avaliações do aluno (data + métricas-chave: peso, % gordura), em ordem cronológica inversa, dentro da ficha (cabeçalho + sub-nav).
- Na sub-nav, a sub-aba "Avaliações" perde o marcador "em breve" (Feedback/Agenda/Financeiro mantêm).
- Estado vazio: sem avaliações, mostra uma frase e um botão "Registar avaliação" apontando para `/alunos/{id}/avaliacoes/nova` (rota criada na issue 04; até lá o botão existe mas leva a 404 — esperado no meio da fatia).
- id de aluno inexistente → 404 no visual da marca.
- Datas exibidas em DD/MM/AAAA; métricas com "sem registro" quando NULL. Nenhum comportamento existente muda (perfil e as outras sub-abas iguais).

## Pré-condições
- Issues 01 e 02 concluídas. `list_avaliacoes` no serviço; a ficha (`ficha.html`) tem o cabeçalho + sub-nav; `get_aluno` no serviço de alunos. 138 testes verdes.

## Arquivos a criar
- `kairos/templates/alunos/ficha_layout.html` — extrai o cabeçalho da ficha (nome, "Voltar", selo de status, botão Editar) + a `<nav class="subnav">` (sub-aba ativa por `subtab`; "Avaliações" SEM "em breve"; as outras 3 com) + `{% block ficha_content %}{% endblock %}`. Contexto esperado: `aluno` (com `id`, `name`, `status_label`, `status_class`) e `subtab`.
- `kairos/avaliacoes/routes.py` — `APIRouter`; `GET /alunos/{aluno_id}/avaliacoes`: `get_aluno` (404 se None) + `list_avaliacoes` → renderiza `avaliacoes/lista.html` com o cabeçalho (via helper `ficha_header`) e `subtab='avaliacoes'`. Rota fina.
- `kairos/templates/avaliacoes/lista.html` — `{% extends "alunos/ficha_layout.html" %}`; no bloco: cartões/linhas de avaliação (data DD/MM/AAAA + peso + % gordura) ou o estado vazio + botão "Registar avaliação".
- `tests/test_avaliacoes_lista.py` — sub-aba mostra as avaliações em ordem data desc; "Avaliações" sem "em breve" e as outras com; estado vazio quando não há avaliações; botão "Registar avaliação"; `/alunos/999/avaliacoes` → 404.

## Arquivos a modificar
- `kairos/web.py` — adicionar helper `ficha_header(aluno: dict) -> dict` retornando `{id, name, status_label, status_class}` (presentação partilhada entre a ficha de alunos e as páginas de avaliação).
- `kairos/templates/alunos/ficha.html` — passa a `{% extends "alunos/ficha_layout.html" %}`; move o conteúdo (o `dl.profile` do perfil e o `.coming-soon` das outras sub-abas) para `{% block ficha_content %}`; remove o cabeçalho + sub-nav duplicados (agora no layout).
- `kairos/alunos/routes.py` — remover a rota `aluno_avaliacoes` (o módulo `avaliacoes` assume `/alunos/{id}/avaliacoes`); `_render_ficha` continua para perfil/feedback/agenda/financeiro. Onde monta o contexto do perfil, garantir que `status_label`/`status_class` continuam disponíveis (já vêm de `_to_profile_display`).
- `kairos/main.py` — `from kairos.avaliacoes.routes import router as avaliacoes_router` + `app.include_router(avaliacoes_router)`.
- `kairos/static/css/components.css` — cartão/linha de avaliação e estado vazio, se o visual pedir (reusar `.card`/`.stats` quando possível).

## Camadas envolvidas
aplicação (rotas avaliacoes + ajustes em alunos/main), frontend (ficha_layout + lista), teste

## Status
concluída
