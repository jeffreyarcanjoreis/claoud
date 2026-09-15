# Ficha do aluno com sub-abas

## Descrição
Comportamento 7 do SPEC: a página do aluno vira "ficha" com sub-navegação (Perfil, Avaliações, Feedback, Agenda, Financeiro); só Perfil tem conteúdo, as outras quatro aparecem "em breve". Monta o esqueleto do drill-down do aluno.

## Depende de
03-alunos-na-marca

## Especificação funcional
- A página do aluno (`/alunos/{id}`) passa a ser uma "ficha": cabeçalho (nome, selo de status, link Voltar, botão Editar) + uma sub-navegação com **Perfil · Avaliações · Feedback · Agenda · Financeiro** + a área de conteúdo.
- Perfil é a sub-aba ativa por padrão em `/alunos/{id}` e mostra a lista de definições do perfil (o conteúdo atual, inalterado).
- As sub-abas Avaliações, Feedback, Agenda e Financeiro têm rota própria (`/alunos/{id}/avaliacoes`, `/feedback`, `/agenda`, `/financeiro`); ao abrir uma, a ficha mostra essa sub-aba ativa e um corpo "em breve" consistente. As quatro têm um marcador "em breve" na sub-nav; Perfil não.
- id inexistente em qualquer rota da ficha (Perfil ou sub-abas) → 404 no visual da marca.
- Casos de borda: o conteúdo do Perfil em `/alunos/{id}` continua idêntico (mesmos rótulos, valores e "sem registro") → os testes de perfil continuam verdes. Nenhuma regra de negócio nova; as sub-abas não têm dados ainda (são fatias futuras).

## Pré-condições
- Issues 01-03 concluídas. `get_aluno` no service; `_to_profile_display` em routes; `.none` e o visual do perfil já vêm de components.css. 84 testes verdes.

## Arquivos a criar
- `kairos/templates/alunos/ficha.html` — a ficha: cabeçalho + sub-nav (aba ativa + marcador "em breve") + conteúdo por sub-aba (o perfil quando `subtab == 'perfil'`, senão o corpo "em breve"). O markup do perfil (a `<dl class="profile">` com os 10 campos + `.none`) vem do atual `perfil.html`, sem alterar rótulos/valores.
- `tests/test_ficha_aluno.py` — verifica: (a) `/alunos/{id}` tem a sub-nav com as 5 sub-abas e Perfil ativo com o conteúdo do perfil; (b) cada rota de sub-aba (`/avaliacoes`, `/feedback`, `/agenda`, `/financeiro`) → 200, com o nome do aluno, a sub-aba certa ativa e o corpo "em breve"; (c) as quatro sub-abas têm marcador "em breve" e Perfil não; (d) `/alunos/999/avaliacoes` → 404.

## Arquivos a modificar
- `kairos/alunos/routes.py` — `GET /alunos/{aluno_id}` passa a renderizar `ficha.html` com `subtab='perfil'` (reusando `_to_profile_display`); adicionar 4 rotas GET (`/alunos/{aluno_id}/avaliacoes`, `/feedback`, `/agenda`, `/financeiro`) que buscam o aluno (404 se não existe) e renderizam `ficha.html` com o `subtab` respetivo e o corpo "em breve". Um helper privado monta o contexto do cabeçalho (id, nome, selo). Registrar as novas rotas sem conflitar com `/editar`, `/novo` e `{aluno_id}` (sufixos literais distintos; `aluno_id` é int).
- `kairos/static/css/components.css` — acrescentar a sub-nav (`.subnav`, aba ativa, marcador "em breve") e um componente `.coming-soon` reutilizável (usado aqui e reaproveitado na issue 06).
- `kairos/templates/alunos/perfil.html` — removido; o seu conteúdo passa a viver em `ficha.html`.

## Camadas envolvidas
aplicação (rotas da ficha), frontend (template ficha + components.css), teste

## Status
concluída
