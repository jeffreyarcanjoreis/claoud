# Anexo da execução (aluno envia por upload)

## Descrição
O aluno anexa um vídeo/foto da execução de um exercício, por **upload de arquivo** guardado localmente (mesmo padrão das fotos/vídeo do app), junto de **observações escritas por ele**, para o coach analisar. Comportamento [F+] 21.

## Depende de
09 (a execução do exercício onde o anexo se prende)

## Status
concluída

## Especificação funcional
O anexo é **por item do treino** (`TreinoItem`): o aluno envia um arquivo (foto OU vídeo) da execução daquele exercício, com uma observação escrita (o verbo é dele; regras 11–14). Pode haver **vários anexos** por item (histórico). Guardado localmente, nome de arquivo gerado pelo servidor (nunca o do cliente). Regra 6: observação vazia = NULL. O feedback do coach é a fatia **12** (não entra aqui).

Reaproveita o módulo de domínio `kairos/execucao/` (models + service) e o padrão de armazenamento de `kairos/treinos/videos.py` / `kairos/alunos/fotos.py`.

- **Dados (migração 0030):** tabela `anexos_execucao` (model `AnexoExecucao`), tipos portáveis:
  - `id` PK autoincrement.
  - `treino_item_id` FK → `treino_itens.id`, `nullable=False`, `index=True`.
  - `filename` `String(64)`, `nullable=False` (arquivo gerado pelo servidor).
  - `tipo` `String(10)`, `nullable=False` (`"imagem"` ou `"video"` — para o template escolher `<img>`/`<video>`).
  - `observacao` `Text`, nullable (observação escrita do aluno).
  - `created_at` `DateTime` `server_default=func.now()`.
  - Registrar o model em `migrations/env.py`. Head 0029 → **0030**.
- **Armazenamento (`kairos/execucao/anexos.py`, novo):** espelha `videos.py`, aceitando **imagem OU vídeo**:
  - `MAX_ANEXO_BYTES = 50 * 1024 * 1024`.
  - `_detect_anexo(data) -> Optional[Tuple[str, str]]`: retorna `(ext, tipo)` — imagem (jpg/png/webp → tipo "imagem") reusando a detecção de `fotos.py`, ou vídeo (mp4/webm/mov → tipo "video") reusando a de `videos.py`; None se nenhum.
  - `save_anexo(file_bytes, content_type, original_filename) -> Tuple[str, str]`: vazio → `ValidationError("O anexo está vazio.")`; tipo não reconhecido → `ValidationError("O anexo precisa ser uma imagem (JPG, PNG, WEBP) ou vídeo (MP4, WEBM, MOV).")`; > MAX → `ValidationError("O anexo é muito grande (máximo 50 MB).")`. Nome = `uuid4().hex + "." + ext` em `config.anexos_dir()`. Retorna `(filename, tipo)`.
  - `delete_anexo_file(filename)`: no-op se falsy; recusa nomes inseguros; apaga se existir.
  - `ValidationError` de `kairos.treinos.service`.
- **Config:** `anexos_dir() -> Path` = `data_dir() / "anexos"`.
- **Serviço (`kairos/execucao/service.py`):**
  - `adicionar_anexo(treino_item_id, file_bytes, content_type, original_filename, observacao=None) -> Dict`: verifica `TreinoItem` existe (senão `ValidationError`); `save_anexo(...)`; cria `AnexoExecucao` com filename/tipo/observação normalizada; loga; retorna dict. Se `save_anexo` falhar, nada é gravado.
  - `list_anexos(treino_item_id) -> List[Dict]`: anexos do item, `created_at` desc.
  - `get_anexo(anexo_id) -> Optional[Dict]`: um anexo (inclui `treino_item_id`, `filename`, `tipo`, `observacao`), ou None.
  - `remove_anexo(anexo_id) -> bool`: get-or-False; guarda filename; apaga a linha; apaga o arquivo; loga; True.
  - `anexos_do_treino(treino_id) -> Dict[int, List[Dict]]`: mapa `treino_item_id → lista de anexos` (para a UI preencher os cards).
- **Rotas (aluno, `kairos/area_aluno/routes.py`):**
  - `POST /aluno/treinos/{treino_id}/itens/{item_id}/anexo` (multipart: `anexo` arquivo, `observacao`): gate do aluno (treino do aluno; item do treino → 404). `adicionar_anexo(...)`; em `ValidationError` no-op (ou reexibir — manter simples, no-op + 303); 303 de volta.
  - `GET /aluno/anexos/{anexo_id}` (serve o arquivo): gate — o anexo deve pertencer a um treino do aluno logado (senão 404); `FileResponse` com media_type por extensão (imagem/vídeo); 404 se arquivo ausente.
  - `POST /aluno/anexos/{anexo_id}/remover`: gate do aluno (anexo de treino do aluno); `remove_anexo`; 303 de volta ao treino.
  - **GET `treino_detalhe`:** enriquecer cada item com `item["anexos"] = anexos_do_treino(...).get(item["id"], [])`.
- **Templates:**
  - `area_aluno/treino_detalhe.html`: no bloco de execução do card, um form `enctype="multipart/form-data"` para enviar anexo (`<input type="file" name="anexo" accept="image/*,video/*">` + textarea `observacao` "o que quero que o coach veja" + enviar), e a **lista** dos anexos existentes do item: cada um com `<img>`/`<video>` (via `/aluno/anexos/{id}`) conforme `tipo`, a observação, e um botão "remover".
  - `treinos/aluno_detalhe.html` (coach): lista read-only dos anexos de cada item (thumb/player + observação do aluno) servidos por uma rota do coach (ver abaixo). O **feedback** é a 12.
- **Rota do coach para servir o anexo:** o coach precisa ver o arquivo. Adicionar `GET /alunos/{aluno_id}/anexos/{anexo_id}` (em `kairos/treinos/routes.py` ou `alunos`) com gate de coach (padrão das rotas de coach), servindo o mesmo arquivo. (Ou uma única rota de servir sem gate de aluno — mas manter o gate: coach vê via rota de coach; aluno via rota de aluno.)
- **CSS:** grade/lista de anexos (thumbs de imagem e vídeo) discreta; form de anexo compacto.

Casos de borda: arquivo não-imagem/não-vídeo ou enorme → `ValidationError`/no-op, nada gravado; anexo de outro aluno → 404 (serve e remover); arquivo órfão (sumiu do disco) → 404 no serve, card degrada; item sem anexos → sem lista (regra 6).

## Pré-condições
- Fatia 09 concluída. Head 0029. Esta fatia adiciona **0030**.
- Padrões de `videos.py`/`fotos.py` (magic bytes) e rota de servir (`aluno_foto`, `exercicio_video`) existem.

## Arquivos a modificar / criar
- `migrations/versions/0030_create_anexos_execucao.py` — nova migração; `migrations/env.py` importa o model.
- `kairos/execucao/models.py` — `AnexoExecucao`.
- `kairos/config.py` — `anexos_dir()`.
- `kairos/execucao/anexos.py` — **novo** (armazenamento imagem+vídeo).
- `kairos/execucao/service.py` — `adicionar_anexo`, `list_anexos`, `get_anexo`, `remove_anexo`, `anexos_do_treino`.
- `kairos/area_aluno/routes.py` — POST anexo, GET servir (aluno), POST remover, enriquecer GET.
- `kairos/treinos/routes.py` — GET servir anexo (coach) + anexos no `_to_item_display`/detalhe do coach.
- `kairos/templates/area_aluno/treino_detalhe.html` — form + lista de anexos (aluno).
- `kairos/templates/treinos/aluno_detalhe.html` — lista de anexos read-only (coach).
- `kairos/static/css/components.css` — estilo dos anexos.

## Camadas envolvidas
- **banco/migração** (`banco-migracao-writer`): `AnexoExecucao` + migração 0030 + env.py.
- **configuração** (`configuracao-writer`): `anexos_dir()`.
- **serviço** (`servico-writer`): `anexos.py` + funções de serviço.
- **aplicação** (`aplicacao-writer`): rotas do aluno (upload/serve/remover) + rota do coach (serve) + enriquecer GETs.
- **frontend** (`frontend-writer`): form + lista de anexos (aluno) e lista read-only (coach) + CSS.
- **testes** (`teste-writer`): `tests/test_treino_anexo.py` + `tests/test_anexo_model.py` — detecção imagem/vídeo (aceita jpg/png/webp/mp4/webm/mov; rejeita outro; tamanho); nome uuid; `adicionar_anexo`/`list_anexos`/`remove_anexo`/`anexos_do_treino`; rotas do aluno (upload grava e GET reflete; serve 200/404; remover; 404 anexo de outro aluno); rota do coach serve com gate; `HEAD_REVISION` 0029→0030 + `test_scaffold`. Suíte completa verde.
