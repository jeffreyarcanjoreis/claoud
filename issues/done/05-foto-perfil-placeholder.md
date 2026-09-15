# Foto no perfil com placeholder

## Descrição
Comportamentos 1 (exibição) e 4: o perfil do aluno mostra a foto no canto superior direito quando existe; quando não há foto, mostra um placeholder honesto "sem foto" (nunca imagem inventada).

## Depende de
03-foto-rota-servir

## Especificação funcional
- No perfil do aluno, a foto aparece no **canto superior direito** do cabeçalho da ficha, quando o aluno tem foto (a imagem vem de `GET /alunos/{id}/foto`).
- Quando o aluno não tem foto, aparece um **placeholder honesto "sem foto"** no mesmo sítio — nunca uma imagem inventada (regra 6).
- A foto/placeholder fica no cabeçalho partilhado da ficha (`ficha_layout`), então mostra-se também nas sub-abas do aluno (a identidade do aluno é consistente) — satisfaz "no perfil" e é coerente.
- Nenhum comportamento existente muda (nome, sub-nav, campos iguais). 226 testes verdes.

## Pré-condições
- Issues 01-04 concluídas: coluna `foto`, a rota `GET /alunos/{id}/foto`, o upload no editar. `ficha_layout.html` é o layout que o perfil e as páginas de avaliação estendem; recebe `aluno` (com `id`, `name`, `status_label`, `status_class`). O dict do aluno já tem `foto` (via `_to_dict`), mas os construtores do contexto da ficha (`ficha_header`, `_to_profile_display`) ainda não o repassam.

## Arquivos a criar
- `tests/test_foto_perfil.py` — aluno COM foto (gravada via `save_foto` + `set_aluno_foto`): `GET /alunos/{id}` contém `<img ... src="/alunos/{id}/foto"`; aluno SEM foto: o perfil mostra "sem foto" (o placeholder) e NÃO tem o `<img src=.../foto`; (bónus) numa sub-aba, ex. `GET /alunos/{id}/avaliacoes`, a foto/placeholder também aparece (mesmo cabeçalho).

## Arquivos a modificar
- `kairos/web.py` — `ficha_header(aluno)` passa a incluir `"foto": aluno.get("foto")` no dict devolvido (para as páginas de avaliação terem a foto no cabeçalho).
- `kairos/alunos/routes.py` — `_to_profile_display(aluno)` passa a incluir `"foto": aluno.get("foto")` (para o perfil ter a foto).
- `kairos/templates/alunos/ficha_layout.html` — reestruturar o topo do `content` num cabeçalho de duas partes: à esquerda o que já existe (h1 nome, "Voltar", mensagem de sucesso, selo, botão Editar); à direita, `{% if aluno.foto %}<img class="ficha-foto" src="/alunos/{{ aluno.id }}/foto" alt="Foto de {{ aluno.name }}">{% else %}<div class="ficha-foto ficha-foto--empty">sem foto</div>{% endif %}`. A sub-nav continua por baixo.
- `kairos/static/css/components.css` — `.ficha-header` (flex: conteúdo à esquerda, foto à direita, alinhado ao topo, wrap em telas estreitas); `.ficha-foto` (ex.: ~120px, quadrada ou 4/5, `object-fit: cover`, borda `--line`, radius); `.ficha-foto--empty` (o placeholder: fundo `--void-2`, texto `--bone-dim` itálico centrado, mesma caixa). Só tokens.

## Camadas envolvidas
aplicação (expor `foto` no contexto da ficha), frontend (layout + css), teste

## Status
concluída
