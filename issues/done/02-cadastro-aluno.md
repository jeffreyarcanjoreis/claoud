# Cadastro de aluno

## Descrição
Comportamentos 1 e 2 do SPEC: o coach cadastra um aluno com nome preenchido e ele passa a existir no sistema; cadastro sem nome é recusado com indicação do campo faltante. Inclui o modelo Aluno com todos os campos do perfil, o endpoint de criação e a página "Novo aluno" com o formulário de perfil.

## Depende de
01-scaffold-banco-migracoes

## Especificação funcional
- `GET /alunos/novo` exibe o formulário "Novo aluno" com todos os campos do perfil do SPEC: nome, data de nascimento, objetivo, fase atual, início do plano, término do plano, restrições físicas, alerta, status (ativo/inativo, default ativo), observações.
- `POST /alunos` com nome preenchido cria o aluno no banco e redireciona (303) de volta para `/alunos/novo` com mensagem de sucesso "Aluno {nome} cadastrado." (o destino muda para a lista na issue 03).
- `POST /alunos` sem nome (vazio ou só espaços) NÃO cria nada e re-renderiza o formulário com status 400, mensagem "Nome é obrigatório." e os demais valores digitados preservados.
- Campos opcionais enviados vazios são gravados como NULL — nunca string vazia nem default inventado (regra 6 do architecture.md).
- Datas chegam de `<input type="date">` (ISO). Data em formato inválido: 400 com mensagem clara, sem gravar nada.
- Validação de período (término < início) NÃO entra aqui — é a issue 07.
- Toda criação gera log (regra 8).
- Convenção de UI definida nesta issue: páginas server-rendered com Jinja2, formulários HTML padrão (POST), sem JavaScript de lógica — thin client/fat server.

## Pré-condições
- Issue 01 concluída (app, banco, migrações, testes — tudo verde).
- Dependências novas: `jinja2` e `python-multipart` (parse de formulário no FastAPI); adicionar ao pyproject e instalar.

## Arquivos a criar
- `kairos/alunos/__init__.py` — módulo de domínio "alunos" (padrão monólito modular)
- `kairos/alunos/models.py` — modelo SQLAlchemy `Aluno` (tabela `alunos`): id, name (obrigatório), birth_date, objective, phase, plan_start, plan_end, restrictions, alert, status (default "active"), notes, created_at; todos os opcionais nullable
- `kairos/alunos/service.py` — `create_aluno(...)`: valida nome obrigatório, normaliza string vazia → None, parse de datas ISO, grava, loga; levanta erro de validação próprio (`ValidationError` do módulo) que a rota traduz em 400
- `kairos/alunos/routes.py` — APIRouter com `GET /alunos/novo` e `POST /alunos`; rotas finas: só traduzem HTTP ↔ serviço
- `kairos/web.py` — instância compartilhada de `Jinja2Templates` apontando para `kairos/templates/`
- `kairos/templates/base.html` — layout base (título Kairos, bloco de conteúdo, CSS mínimo embutido)
- `kairos/templates/alunos/novo.html` — formulário completo, exibição de erro e de sucesso, valores preservados em caso de erro
- `migrations/versions/0002_create_alunos.py` — cria a tabela `alunos` (down_revision "0001"); tipos portáveis (String, Date, DateTime, Text) — nada específico de SQLite
- `tests/test_cadastro_aluno.py` — cobre: criação com sucesso grava no banco; sem nome → 400 e nada gravado; só espaços → 400; opcionais vazios viram NULL; data inválida → 400; status default "active"; formulário abre com 200

## Arquivos a modificar
- `pyproject.toml` — adicionar `jinja2` e `python-multipart` às dependências
- `kairos/main.py` — incluir o router de alunos (uma linha de `include_router`)
- `migrations/env.py` — importar `kairos.alunos.models` para o metadata conhecer a tabela (necessário para autogenerate futuro)

## Camadas envolvidas
modelo/migração, serviço, rota/página (template), teste

## Status
concluída
