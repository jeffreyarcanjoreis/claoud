# Issue 24 — Arquivar/excluir aluno + detecção de duplicado na conversão

## Status
concluída

## Contexto / decisão do PO
Dois pontos que faltavam pra gestão do ciclo lead→aluno:
1. **Arquivar / excluir aluno** — hoje não dá pra tirar um aluno criado por engano
   nem pra "aposentar" um aluno que saiu.
2. **Detecção de duplicado na conversão** — hoje "Transformar em aluno" sempre cria
   um aluno novo, mesmo que já exista um com o mesmo nome.

---

## PARTE 1 — Arquivar / excluir aluno

Duas ações, com pesos diferentes (proteção contra perda de dados):

### Arquivar / Reativar (soft, reversível)
- O Aluno já tem `status` (active/inactive). "Arquivar" = `status="inactive"`;
  "Reativar" = `status="active"`. Reversível, **nunca perde dado**.
- Serviço `alunos/service.py`: `arquivar_aluno(id)` / `reativar_aluno(id)` (ou um
  `set_status(id, status)`), retornando o aluno ou None.
- Rotas: `POST /alunos/{id}/arquivar` e `POST /alunos/{id}/reativar` → redirect pra ficha.
- Ficha do aluno: botão "Arquivar" (quando active) / "Reativar" (quando inactive),
  + um selo visível quando o aluno está arquivado. A lista de Alunos já filtra por
  status (os arquivados aparecem só na visão "todos", não em "ativos").

### Excluir (hard, permanente, com trava de segurança)
- Excluir de vez é irreversível. Regra de segurança (regra 6 / não perder dado):
  **só permite excluir quando o aluno NÃO tem histórico** — sem avaliações, treinos,
  sessões agendadas, sessões realizadas, planos ou pagamentos. É o caso do "criado por
  engano". Se tiver histórico, o app NÃO exclui: orienta a **arquivar** no lugar.
- Serviço: `aluno_tem_historico(id) -> bool` (conta linhas nas tabelas com FK
  aluno_id: avaliacoes, treinos, sessoes_agendadas, sessoes_realizadas, planos_aluno,
  pagamentos). `excluir_aluno(id) -> str` ("nao_encontrado" | "tem_historico" | "ok");
  no "ok", apaga a linha do Aluno E o arquivo da foto (via `delete_foto_file`).
- Rotas (confirmação obrigatória — ação destrutiva):
  - `GET /alunos/{id}/excluir` → página de confirmação: aviso "Esta ação é permanente";
    se `aluno_tem_historico`, NÃO mostra o botão de excluir — mostra o aviso de que o
    aluno tem histórico e o caminho é arquivar (link/botão arquivar).
  - `POST /alunos/{id}/excluir` → chama `excluir_aluno`; "ok"→redirect pra `/alunos`;
    "tem_historico"→re-renderiza a confirmação com o aviso; "nao_encontrado"→404.
- Ficha: botão "Excluir" discreto (leva à confirmação), separado do arquivar.

---

## PARTE 2 — Detecção de duplicado na conversão

Ao "Transformar em aluno", checar se já existe um aluno com o mesmo nome antes de criar.
- `alunos/service.py` já tem `find_aluno_by_name(nome)` (case-insensitive). Reusar.
- `contatos/service.py::converter_contato_em_aluno(contato_id, force=False)`:
  - se `force=False` e existe aluno com o mesmo nome → **não cria**; sinaliza
    duplicado (ex.: retorna um dict `{"duplicado": True, "aluno_existente_id": X,
    "aluno_existente_nome": ...}` em vez do id; ou levanta uma exceção própria
    `AlunoDuplicado`). Escolher a forma mais limpa e consistente com o código.
  - se `force=True` → cria mesmo assim (fluxo atual).
- Rota `POST /contatos/{id}/converter`:
  - sem duplicado → cria e redireciona pra `/alunos/{novo_id}` (como hoje).
  - com duplicado (e sem force) → re-renderiza o **detalhe da lead** com um aviso:
    "Já existe um aluno chamado 'X'." + dois caminhos: (a) botão "Ver aluno existente"
    → `/alunos/{existente_id}`; (b) botão "Criar novo mesmo assim" → repõe o POST com
    `force=1` (hidden field).
- Detalhe da lead: renderizar esse aviso + os dois botões quando o contexto trouxer
  `duplicado`.

---

## Testes
Parte 1:
- Serviço: arquivar/reativar mudam status; `aluno_tem_historico` True quando há
  qualquer dependente (testar com uma avaliação/pagamento), False quando limpo;
  `excluir_aluno` → "ok" apaga o aluno (e não deixa órfão), "tem_historico" não apaga,
  "nao_encontrado" para id inexistente.
- Rotas: POST arquivar/reativar mudam o status e redirecionam; `GET /alunos/{id}/excluir`
  mostra confirmação e, com histórico, esconde o botão excluir; `POST .../excluir`
  apaga (sem histórico) e redireciona pra /alunos; bloqueia (com histórico); 404.
- Ficha mostra o selo "arquivado" e os botões certos por status.
Parte 2:
- `converter_contato_em_aluno`: sem duplicado cria; com nome já existente e force=False
  sinaliza duplicado sem criar; force=True cria mesmo assim.
- Rota converter: duplicado → detalhe com o aviso + os dois botões; "criar mesmo assim"
  (force) cria e redireciona.
Rodar a suíte inteira; reportar verde. (Sem migração nesta fatia — head segue 0017.)

## Fora de escopo
- Exclusão em cascata de aluno COM histórico (decidido: bloquear e orientar arquivar).
- Merge de leads/alunos duplicados (só avisamos; não fundimos).

## Camadas / subagentes
servico-writer (alunos: set_status/arquivar/reativar, aluno_tem_historico,
excluir_aluno; contatos: force + duplicado no converter) → aplicacao-writer (rotas
arquivar/reativar/excluir[GET+POST] + force/duplicado no converter + contexto do
detalhe e da ficha) → frontend-writer (botões/selo na ficha, página de confirmação de
exclusão, aviso de duplicado no detalhe da lead) → teste-writer (suíte). Sem
banco-migracao (nenhuma coluna nova).
