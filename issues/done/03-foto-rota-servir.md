# Rota que serve a foto

## Descrição
Comportamentos 2 e 3: `GET /alunos/{id}/foto` devolve o ficheiro da foto do aluno com o content-type correto; responde 404 quando o aluno não tem foto ou não existe.

## Depende de
02-foto-servico-armazenamento

## Especificação funcional
- `GET /alunos/{aluno_id}/foto` devolve o ficheiro da foto do aluno com o content-type correto (jpg→`image/jpeg`, png→`image/png`, webp→`image/webp`) quando o aluno tem foto e o ficheiro existe em disco.
- Responde **404** quando: o aluno não existe, o aluno não tem foto (`foto` NULL), ou o campo `foto` aponta para um ficheiro que já não está no disco (órfão) — nunca rebenta com 500.
- Rota fina: só lê o campo `foto` do aluno e serve o ficheiro de `fotos_dir()`; nenhuma regra de negócio.
- Ordem de registo: `/alunos/{aluno_id}/foto` é sufixo literal (como `/editar`), não colide com as rotas existentes; `aluno_id` é int.

## Pré-condições
- Issues 01 e 02 concluídas: coluna `foto` + `_to_dict` a expô-la; `config.fotos_dir()`; `save_foto`/`set_aluno_foto` para os testes criarem uma foto. `get_aluno` no serviço de alunos. 214 testes verdes.

## Arquivos a criar
- `tests/test_foto_rota.py` — (a) aluno com foto (gravada via `kairos.alunos.fotos.save_foto` + `set_aluno_foto`): `GET /alunos/{id}/foto` → 200, content-type de imagem, e o corpo são os bytes gravados; (b) aluno sem foto → 404; (c) aluno inexistente → 404; (d) `foto` definido mas o ficheiro apagado do disco → 404 (não 500).

## Arquivos a modificar
- `kairos/alunos/routes.py` — acrescentar `GET /alunos/{aluno_id}/foto`: `aluno = get_aluno(aluno_id)`; se None ou `aluno["foto"]` None → `Response(status_code=404)` (ou uma resposta 404 simples). Senão `path = config.fotos_dir() / aluno["foto"]`; se `not path.exists()` → 404; senão `FileResponse(path, media_type=<pelo ext>)`. Um helper/dict privado mapeia extensão → media_type. Importar `FileResponse` de `fastapi.responses` e `config`. Registar a rota junto das outras `/alunos/{aluno_id}/...`.

## Camadas envolvidas
aplicação (rota que serve o ficheiro), teste

## Status
concluída
