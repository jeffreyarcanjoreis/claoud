# Vídeo de demonstração no exercício (upload)

## Descrição
Um exercício da biblioteca pode ter um vídeo de demonstração, enviado por **upload de arquivo** e guardado localmente (mesmo padrão das fotos do app). O vídeo aparece no card do exercício, na planilha do coach e do aluno. Comportamentos [F+] 14 e 15.

## Depende de
nenhuma

## Status
planejada

## Especificação funcional
Espelha o fluxo de foto do aluno (`kairos/alunos/fotos.py` + rota de servir + rota de upload), aplicado ao `Exercicio`. O vídeo é **por exercício** (da biblioteca), não por item do treino — assim vale para toda planilha que use aquele exercício.

- **Dados (migração 0026):** adicionar coluna `video_filename` (`String(64)`, nullable) à tabela `exercicios`. Model `Exercicio` ganha `video_filename: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)`. `_to_dict(exercicio)` passa a incluir `"video_filename"`. Head passa de 0025 → **0026**.
- **Armazenamento (`kairos/treinos/videos.py`, novo — espelha `fotos.py`):**
  - `MAX_VIDEO_BYTES = 50 * 1024 * 1024` (50 MB).
  - `_detect_video_ext(data)` por magic bytes: MP4 (`....ftyp` no offset 4), WEBM (`\x1a\x45\xdf\xa3` — container Matroska/WebM), QuickTime/MOV (`....ftypqt` ou `....moov`/`....ftyp` com brand `qt`); retorna `"mp4"`/`"webm"`/`"mov"` ou None. Nunca confiar no content-type/filename do cliente.
  - `save_video(file_bytes, content_type, original_filename) -> str`: valida vazio → `ValidationError("O vídeo está vazio.")`; tipo não reconhecido → `ValidationError("O vídeo precisa ser um arquivo de vídeo (MP4, WEBM ou MOV).")`; tamanho > MAX → `ValidationError("O vídeo é muito grande (máximo 50 MB).")`. Nome no disco = `uuid4().hex + "." + ext` (nunca o nome do cliente). Grava em `config.videos_dir()` (criar dir). Loga e retorna o filename.
  - `delete_video_file(filename)`: no-op se falsy; recusa nomes inseguros (contém `/`, `\`, `..`); apaga se existir; apagar inexistente não é erro.
  - `ValidationError` reaproveitada de `kairos.treinos.service` (mesmo módulo de domínio).
- **Config:** `videos_dir() -> Path` = `data_dir() / "videos"` (junto de `fotos_dir()`).
- **Serviço (`kairos/treinos/service.py`):**
  - `set_exercicio_video(exercicio_id, file_bytes, content_type, original_filename) -> Optional[Dict]`: get-or-None; chama `save_video`; apaga o vídeo antigo (`delete_video_file`) só **depois** de gravar o novo com sucesso; grava `video_filename`; loga; retorna o exercício atualizado (dict). Se `save_video` levantar `ValidationError`, nada muda (o antigo permanece).
  - `remove_exercicio_video(exercicio_id) -> bool`: get-or-False; guarda o filename atual; zera `video_filename` (→ None, "sem registro"); apaga o arquivo; loga; retorna True.
  - `get_treino_detail` e `add_item_to_treino` já retornam item; o item passa a expor também `video_filename` do exercício (join já traz o Exercicio) para o card decidir se mostra o player. (Adicionar `video_filename` ao select/dict de `get_treino_detail`.)
- **Rotas (`kairos/treinos/routes.py`):**
  - `GET /exercicios/{exercicio_id}/video`: serve o arquivo (padrão da rota `aluno_foto`): 404 quando exercício não existe, sem vídeo, ou arquivo ausente do disco; `FileResponse` com media_type por extensão (`video/mp4`, `video/webm`, `video/quicktime`).
  - `POST /exercicios/{exercicio_id}/video` (multipart, campo `video`): get-or-404; lê bytes; `set_exercicio_video(...)`; em `ValidationError` volta com a mensagem (mesmo tratamento de erro das outras rotas de treino — reexibir com erro, sem 500); 303 de volta para a origem (a planilha do treino, via `next`/referer se o padrão do projeto usar, senão para a biblioteca de exercícios / detalhe do treino).
  - `POST /exercicios/{exercicio_id}/video/remover`: get-or-404; `remove_exercicio_video`; 303 de volta.
- **Templates:**
  - Planilha do coach (`kairos/templates/treinos/aluno_detalhe.html`): no card/linha do exercício, quando `i.video_filename` existir, um `<video controls preload="metadata" src="/exercicios/{{ i.exercicio_id }}/video">` discreto (ou um botão/thumb que revela o player). Form de upload (multipart) por exercício **na área do coach** — o mais simples que caiba: um `<details>` "Vídeo de demonstração" com `<input type="file" name="video" accept="video/*">` + enviar, e, havendo vídeo, um botão "Remover vídeo".
  - Planilha do aluno (`kairos/templates/area_aluno/treino_detalhe.html`): read-only — quando houver vídeo, mostra o `<video controls>` no card do exercício (o aluno não envia nem remove).
- **CSS:** estilos discretos para o player/thumb dentro da planilha (usar tokens existentes; player com `max-width:100%` e `border-radius: var(--radius)`).

Casos de borda: exercício inexistente → 404 nas três rotas; upload de arquivo não-vídeo/enorme → `ValidationError` reexibida, vídeo antigo intacto; exercício sem vídeo → card sem player, sem quebrar; filename órfão (arquivo sumiu do disco) → 404 no serve, card degrada sem 500.

## Pré-condições
- Head atual 0025 (fatias 01–05 concluídas). Esta fatia adiciona a migração **0026**.
- `Exercicio` já tem `_to_dict`; `get_treino_detail` já faz join com `Exercicio`.

## Arquivos a modificar / criar
- `migrations/versions/0026_add_video_to_exercicios.py` — nova migração.
- `kairos/treinos/models.py` — coluna `video_filename` em `Exercicio`.
- `kairos/config.py` — `videos_dir()`.
- `kairos/treinos/videos.py` — **novo** (armazenamento, espelha `fotos.py`).
- `kairos/treinos/service.py` — `_to_dict`/`get_treino_detail` incluem `video_filename`; `set_exercicio_video`, `remove_exercicio_video`.
- `kairos/treinos/routes.py` — GET serve + POST upload + POST remover.
- `kairos/templates/treinos/aluno_detalhe.html` — player + form upload/remover (coach).
- `kairos/templates/area_aluno/treino_detalhe.html` — player read-only (aluno).
- `kairos/static/css/components.css` — estilo do player/thumb.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): migração 0026 + coluna no model.
- **configuração** (`configuracao-writer`): `videos_dir()` em config.py.
- **serviço** (`servico-writer`): `videos.py`, `set_exercicio_video`, `remove_exercicio_video`, `video_filename` no detail/dict.
- **aplicação** (`aplicacao-writer`): rotas serve/upload/remover.
- **frontend** (`frontend-writer`): player + forms (coach) e player read-only (aluno) + CSS.
- **testes** (`teste-writer`): `tests/test_treino_video.py` — magic-byte detection (mp4/webm/mov aceitos; não-vídeo rejeitado; tamanho excedido rejeitado); nome no disco é uuid (não o do cliente); `set_exercicio_video` troca o arquivo e apaga o antigo só após sucesso; `remove_exercicio_video` zera e apaga; rota GET serve 200/404 (sem exercício, sem vídeo, órfão); POST upload grava e reflete no `get_treino_detail`; POST inválido reexibe erro sem trocar; POST remover; bump de `HEAD_REVISION` 0025→0026 nos arquivos que fixam a head; `test_exercicio_model`/afins ganham a coluna nova. Suíte completa verde.
