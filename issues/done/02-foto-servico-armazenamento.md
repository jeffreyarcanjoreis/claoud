# Serviço de armazenamento da foto

## Descrição
Comportamentos 5, 7, 8, 9 (lado da regra): guardar uma imagem enviada em disco (data/fotos/, sob KAIROS_DATA_DIR) com nome de ficheiro seguro e único gerado pelo servidor; validar tipo (jpg/jpeg/png/webp) e tamanho máximo; substituir apaga o ficheiro antigo; remover apaga o ficheiro e limpa o campo. Toda a regra no serviço.

## Depende de
01-foto-modelo-migracao

## Especificação funcional
- `save_foto(file_bytes, content_type, original_filename) -> str`: valida e grava uma imagem em `fotos_dir()`, devolvendo o nome do ficheiro gerado.
  - **Validação de tipo por magic bytes** (não confiar na content-type do cliente): aceita só JPEG (`FF D8 FF`), PNG (`89 50 4E 47 0D 0A 1A 0A`) e WEBP (`RIFF`…`WEBP`); qualquer outra coisa → `ValidationError("A foto precisa ser uma imagem (JPG, PNG ou WEBP).")`.
  - **Tamanho**: `len(file_bytes) > MAX_FOTO_BYTES` (~5 MB) → `ValidationError("A foto é muito grande (máximo 5 MB).")`. Ficheiro vazio (0 bytes) também é recusado.
  - **Nome seguro**: gerado pelo servidor — `uuid4().hex + "." + ext`, onde `ext` vem do tipo DETETADO (jpg/png/webp), nunca do nome do cliente. O nome do cliente nunca entra no caminho em disco (defesa contra path traversal).
  - grava os bytes em `fotos_dir()/<nome>`, criando a pasta se preciso; devolve o nome.
- `delete_foto_file(filename)`: apaga `fotos_dir()/<filename>` se existir; ignora se não existe; recusa nomes que não sejam um nome-base simples (sem `/`, `\`, `..`).
- `set_aluno_foto(aluno_id, filename: Optional[str]) -> dict | None`: atualiza a coluna `foto` do aluno (nome ou None) e devolve o dict do aluno, ou None se o aluno não existe.
- Toda a regra e o I/O vivem no servidor; funções recebem primitivos (bytes/str), não objetos web (testáveis sem FastAPI).

## Pré-condições
- Issue 01 concluída: coluna `foto`, `_to_dict` expõe `foto`. `ValidationError` existe em `kairos/alunos/service.py`. `config.py` tem `data_dir()`/`backups_dir()` como referência. 200 testes verdes.

## Arquivos a criar
- `kairos/alunos/fotos.py` — módulo de armazenamento de fotos: `MAX_FOTO_BYTES`, `save_foto(...)`, `delete_foto_file(...)`; a deteção de tipo por magic bytes num helper privado. Importa `ValidationError` de `kairos.alunos.service` (mesmo tipo que a rota de editar já captura). Usa `config.fotos_dir()`.
- `tests/test_foto_servico.py` — save com PNG/JPEG/WEBP mínimos válidos (bytes com o magic certo) grava e devolve um nome `*.png/.jpg/.webp`; o ficheiro existe em fotos_dir; save com bytes que não são imagem → ValidationError; save acima do limite → ValidationError; save de 0 bytes → ValidationError; o nome devolvido é um UUID (não o nome original passado); `delete_foto_file` remove o ficheiro e é seguro se não existe; `delete_foto_file` recusa nome com `..`/`/`; `set_aluno_foto` grava e lê o nome, e None limpa; `set_aluno_foto` de id inexistente → None.

## Arquivos a modificar
- `kairos/config.py` — acrescentar `fotos_dir()` = `data_dir() / "fotos"` (a par de `backups_dir()`).
- `kairos/alunos/service.py` — acrescentar `set_aluno_foto(aluno_id, filename)` (update da coluna `foto` via `session_scope`; devolve `_to_dict` ou None). Sem tocar em `create_aluno`/`update_aluno`.

## Camadas envolvidas
configuração (fotos_dir), serviço (armazenamento de ficheiro + set_aluno_foto), teste

## Status
concluída
