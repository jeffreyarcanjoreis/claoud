# Início do painel com contagens

## Descrição
Comportamentos 4, 5 e 13 do SPEC: a raiz do app (`/`) passa a abrir o Início (deixa de redirecionar para Alunos); o Início mostra contagens reais (total de alunos e ativos) e marca "em breve" o que ainda não tem dados. O teste que verificava o redirect de `/` é atualizado para o novo comportamento.

## Depende de
02-shell-painel

## Especificação funcional
- `GET /` deixa de redirecionar e passa a renderizar a página **Início** no visual da marca, dentro do shell.
- A aba "Início" fica ativa em `/` (já suportado pelo shell, que calcula a aba de `request.url.path`).
- O Início mostra contagens **reais**: total de alunos e alunos ativos (lidos do banco).
- O que ainda não tem fonte de dados (sessões de hoje, financeiro) aparece com marcador "em breve", nunca com número inventado (regra 6).
- Casos de borda: com zero alunos, as contagens mostram 0 (não "em breve" — 0 é um dado real). `GET /health` continua a responder `{"status":"ok"}`.
- Mudança de comportamento assumida: os testes que verificavam `GET / → 307 redirect para /alunos` passam a verificar o Início. São atualizados nesta issue.

## Pré-condições
- Issues 01-04 concluídas. Shell no base.html; `list_alunos(status=...)` no service; `templates` em `kairos/web.py`; `.coming-soon` e o visual da marca disponíveis. 102 testes verdes.

## Arquivos a criar
- `kairos/painel/__init__.py` — novo módulo para as páginas de nível do painel (Início agora; as áreas "em breve" da issue 06 entram aqui depois).
- `kairos/painel/routes.py` — `APIRouter` com `GET /` que lê as contagens (via service) e renderiza `painel/inicio.html`.
- `kairos/templates/painel/inicio.html` — a página Início: eyebrow + saudação (h1), tiles com as contagens reais (Alunos, Ativos) e marcadores "em breve" para o que ainda não tem dados (Sessões de hoje, Financeiro).
- `tests/test_inicio.py` — verifica: `GET /` → 200 (não redirect) e mostra o Início; a aba Início está ativa em `/`; as contagens reais aparecem (cria N alunos, M ativos, confere os números); "em breve" presente para as áreas sem dados; com zero alunos mostra 0.

## Arquivos a modificar
- `kairos/main.py` — remover o `@app.get("/")` (redirect) e incluir o `painel_router`. `/health` fica.
- `kairos/alunos/service.py` — adicionar `count_alunos() -> dict` (`{"total": int, "active": int}`) com uma query de contagem (fat server; não carregar tudo para contar).
- `kairos/static/css/components.css` — acrescentar os tiles de estatística (`.stats`, `.stat`, `.stat .n`, `.stat .l`) e o cabeçalho do Início, usando as custom properties. (`.coming-soon` já existe da issue 04.)
- `tests/test_lista_alunos.py` e `tests/test_shell_painel.py` — atualizar as asserções de `GET /` (era redirect 307 para `/alunos`) para o novo comportamento (200, Início).

## Camadas envolvidas
aplicação (módulo painel + main.py), serviço (contagem), frontend (inicio.html + components.css), teste

## Status
concluída
