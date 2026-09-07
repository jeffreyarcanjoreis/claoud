# Upload da foto no formulário de editar

## Descrição
Comportamentos 1, 6, 7, 8, 10 (lado da UI/rota): o formulário de editar ganha um campo de envio de foto e a opção "remover foto"; o POST passa a multipart e chama o serviço de armazenamento; enviar imagem válida guarda a foto; ficheiro inválido/grande → 400 com mensagem, sem alterar nada; guardar sem ficheiro mantém a foto atual.

## Depende de
02-foto-servico-armazenamento

## Especificação funcional
- O formulário de editar (`/alunos/{id}/editar`) mostra um campo de envio de foto (`<input type="file">`); o `<form>` passa a `enctype="multipart/form-data"`.
- Quando o aluno já tem foto, o editar mostra uma pré-visualização (a foto atual) e uma opção "remover foto".
- `POST /alunos/{id}` com uma imagem válida guarda a foto (via o serviço da issue 02) e o aluno passa a ter foto; redireciona 303 para o perfil.
- Ficheiro que não é imagem, ou acima do limite → 400, re-render do editar com a mensagem, **sem alterar nada** (nem a foto nem os campos de texto).
- Texto inválido (ex.: período com término antes do início) → 400, e a foto também não é aplicada (atomicidade: se a foto nova já foi escrita em disco, é apagada no rollback).
- "Remover foto" marcado + guardar → o campo `foto` fica NULL e o ficheiro é apagado; o perfil volta ao placeholder.
- Substituir: enviar nova foto apaga o ficheiro antigo do disco.
- Guardar sem enviar ficheiro (e sem "remover") mantém a foto atual inalterada.
- O campo de foto NÃO aparece no formulário de *novo* aluno (só no editar).

## Pré-condições
- Issues 01-03 concluídas: `save_foto`/`delete_foto_file`/`set_aluno_foto`, a rota `GET /alunos/{id}/foto`. O form partilhado `_form.html` (novo+editar), a rota GET editar e POST update existem. 218 testes verdes.

## Fluxo da rota POST (atomicidade)
1. `aluno0 = get_aluno(aluno_id)`; None → 404. `old_foto = aluno0["foto"]`; `has_foto = bool(old_foto)`.
2. Ler o upload: `uploaded = foto is not None and foto.filename`; se uploaded, `data = await foto.read()`; `new_foto = save_foto(data, foto.content_type, foto.filename)` — `ValidationError` → re-render 400 (com contexto do editar + show_foto/has_foto), nada gravado (save_foto valida antes de escrever).
3. `update_aluno(text...)` — `ValidationError` → se `new_foto` foi escrita, `delete_foto_file(new_foto)` (rollback); re-render 400.
4. Aplicar foto: se `remover_foto` → `set_aluno_foto(id, None)` + `delete_foto_file(old_foto)`; senão se `new_foto` → `set_aluno_foto(id, new_foto)` + `delete_foto_file(old_foto)`; senão manter.
5. RedirectResponse 303 para `/alunos/{id}?atualizado=1`.

## Arquivos a criar
- `tests/test_foto_upload.py` — GET editar mostra o input de foto e o form é multipart; POST com PNG válido (TestClient `files={"foto": ("x.png", png_bytes, "image/png")}` + `data` com name) → 303 e a foto fica definida (get_aluno + GET /foto 200); POST com ficheiro não-imagem → 400 e nada mudou (foto None, name igual); substituir uma foto por outra apaga o ficheiro antigo (o nome antigo já não existe em disco); "remover foto" (`data={"remover_foto":"1", ...}`) → foto None e GET /foto 404; POST só com texto (sem `files`) → foto inalterada; **atomicidade**: com foto existente, POST com texto inválido + imagem válida → 400 e a foto continua a antiga (não trocou).

## Arquivos a modificar
- `kairos/templates/alunos/_form.html` — `enctype="multipart/form-data"` no `<form>`; `{% if show_foto %}` uma secção "Foto": se `has_foto`, `<img class="foto-atual" src="/alunos/{{ aluno_id }}/foto" alt="Foto do aluno">` + `<label><input type="checkbox" name="remover_foto" value="1"> Remover foto</label>`; sempre `<input type="file" id="foto" name="foto" accept="image/png,image/jpeg,image/webp">`.
- `kairos/alunos/routes.py` — imports `File`, `UploadFile` (fastapi), `save_foto`/`delete_foto_file` (kairos.alunos.fotos), `set_aluno_foto` (service). GET editar: acrescentar `"show_foto": True, "has_foto": bool(aluno["foto"])` ao contexto. POST update: acrescentar params `foto: Optional[UploadFile] = File(None)` e `remover_foto: Optional[str] = Form(None)`, e implementar o fluxo acima; as re-renders de erro do editar incluem `show_foto`/`has_foto`. (O form de *novo* não passa `show_foto`, então o campo não aparece; a rota POST /alunos de criação não muda.)
- `kairos/static/css/components.css` — (opcional) estilo mínimo da `.foto-atual` (miniatura arredondada) e do campo, só tokens.

## Camadas envolvidas
aplicação (rota multipart + fluxo), frontend (form + css), teste

## Status
concluída
