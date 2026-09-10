# Frente do aluno (coach define/ajusta)

## Descrição
Cada aluno passa a ter uma frente principal entre Performance, Saúde Integrada e Longevidade. Na ficha do aluno, o coach vê a frente atual (ou "sem registro") e a define ou troca por uma das três; uma frente fora do conjunto é recusada. Uma frente principal por aluno nesta fatia.

## Depende de
nenhuma

## Status
concluída

## Especificação funcional
A `frente` é um atributo do aluno (como os demais campos de perfil), definido pelo coach por uma **mutação focada** (padrão de `set_status`/`set_aluno_foto`), não pelo formulário grande de edição.

- **Vocabulário (fonte única, no serviço de alunos):**
  - `FRENTE_OPCOES = ("performance", "saude_integrada", "longevidade")`
  - `FRENTE_LABELS = {performance: "Performance", saude_integrada: "Saúde Integrada", longevidade: "Longevidade"}`
  - `FRENTE_SIGNIFICADOS` = frase curta pt-BR por frente (o corpo agora / o corpo equilibrado / o corpo no tempo longo). Definido aqui porque a frente é do aluno; o lado do aluno (issue 03) importa daqui.
- **`set_frente(aluno_id, frente)`:**
  - normaliza vazio/whitespace → `None` (escolher "—" limpa, volta a "sem registro", regra 6);
  - se preenchido e não ∈ `FRENTE_OPCOES` → `ValidationError("Frente inválida.")`, nada é gravado;
  - grava a frente (substitui a anterior — uma principal por aluno); **loga** a escrita (regra 8);
  - retorna o dict do aluno, ou `None` quando `aluno_id` não existe (a rota trata 404).
- **`_to_dict` do aluno** passa a expor `frente`, `frente_label` (ou `None`) e `frente_significado` (ou `None`).
- **Exibição (aba Perfil da ficha):** uma seção "Frente" mostra a frente atual (label) ou "sem registro" (mesmo padrão visual `.none`/"sem registro" das outras linhas), com um `<select>` (as 3 opções + "—") e um botão que envia para a rota abaixo, com a opção atual pré-selecionada.
- **Rota `POST /alunos/{aluno_id}/frente`:** 404 se o aluno não existe; chama `set_frente`; `ValidationError` → volta à ficha com a mensagem (sem gravar); sucesso → `RedirectResponse` 303 para `/alunos/{aluno_id}?atualizado=1` (reusa o `success` "Perfil atualizado." já existente na ficha).

Casos de borda: aluno inexistente → 404 (nunca 500); frente fora do conjunto → recusada sem gravar; "—" → limpa (NULL); trocar por outra das três → substitui.

## Pré-condições
- Domínio `alunos` e a ficha do coach existem (aba Perfil em `ficha.html`). HEAD de migração: **0022**.

## Arquivos a criar
- `migrations/versions/0023_add_frente_to_alunos.py` — `upgrade()` adiciona a coluna `frente` (`String(20)`, nullable) em `alunos`; `downgrade()` remove. Tipos portáveis; sem default (NULL = sem registro). `down_revision = "0022"`.

## Arquivos a modificar
- `kairos/alunos/models.py` — adicionar `frente: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)` em `Aluno`.
- `kairos/alunos/service.py` — constantes `FRENTE_OPCOES`/`FRENTE_LABELS`/`FRENTE_SIGNIFICADOS`; função `set_frente()`; incluir `frente`/`frente_label`/`frente_significado` em `_to_dict`. **Não** mexer em `create_aluno`/`update_aluno`/`_clean_fields` (frente é mutação focada).
- `kairos/alunos/routes.py` — nova rota `POST /alunos/{aluno_id}/frente` (importa `set_frente`, `FRENTE_OPCOES`, `FRENTE_LABELS`); montar a lista de opções de display para o template. Registrar junto das outras ações POST da ficha (arquivar/reativar).
- `kairos/templates/alunos/ficha.html` — na aba `perfil`, seção "Frente": exibição (label ou "sem registro") + `<form method="post" action="/alunos/{{ aluno.id }}/frente">` com `<select name="frente">` (opções + "—", atual selecionada) e botão salvar.
- `kairos/static/css/` — só se faltar estilo; reaproveitar classes existentes (`.profile`, `.row`, `.none`, `button-link`). Provavelmente sem CSS novo.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): coluna `frente` + migração 0023.
- **serviço** (`servico-writer`): `FRENTE_*` + `set_frente` + `_to_dict`.
- **aplicação** (`aplicacao-writer`): rota `POST /alunos/{aluno_id}/frente`.
- **frontend** (`frontend-writer`): seção "Frente" na aba Perfil da ficha.
- **testes** (`teste-writer`): `set_frente` (válida, inválida, limpar, aluno inexistente, substituição); a rota (redirect 303, 404, inválida não grava); exibição na ficha (frente atual e "sem registro"). Suíte anterior verde.
