# Issue 23 — Transformar a lead em aluno (puxando o perfil completo)

## Status
concluída

## Contexto / decisão do PO
Fechar o ciclo: um botão na lead (Contato vindo do cadastro) **cria um Aluno com o
perfil já preenchido**. O PO escolheu a versão **completa**: expandir o modelo de
Aluno com os campos que faltam, pra a conversão puxar TUDO estruturado (nada de
despejar dados num bloco de texto) e a ficha do aluno passar a mostrar esses dados.

## Descompasso a resolver
A lead (Contato) coleta mais do que o Aluno sabe guardar hoje. O Aluno tem: name,
birth_date, objective, phase, plan_start/end, restrictions, alert, status, notes,
foto. Faltam: **contato, sexo, idade (a lead pergunta idade, não data de
nascimento), frequência, nível de condicionamento, condições/patologias,
medicamentos**.

## 1. Expandir o modelo `Aluno` (migração 0017, head atual 0016 → 0017; ALTER add columns)
Novas colunas, todas nullable (regra 6):
- `contact` String(200) — contato (telefone/@/e-mail)
- `sex` String(30) — masculino/feminino/outro/nao_informado
- `age_reported` Integer — idade informada no cadastro (não sobrescreve birth_date;
  a ficha mostra a idade calculada de birth_date quando houver, senão a informada)
- `weekly_frequency` String(20) — 1-2 / 3-4 / 5+
- `conditioning_level` String(20) — sedentario/iniciante/intermediario/avancado
- `health_conditions` Text — condições / patologias
- `medications` Text — medicamentos em uso
(`restrictions` já existe → lesões / restrições.)

## 2. Serviço `alunos/service.py`
- Constantes (independentes, pra não criar ciclo com contatos): `SEX_OPCOES`+labels,
  `CONDITIONING_LEVELS`+labels, `WEEKLY_FREQUENCIES`+labels (mesmos valores usados no
  cadastro).
- `_clean_fields` / `create_aluno` / `update_aluno` ganham os novos parâmetros:
  normaliza texto (vazio→None); `age_reported` inteiro 1..120 opcional; sex/
  conditioning_level/weekly_frequency validados contra as opções.
- `_to_dict` inclui os novos campos + rótulos (`sex_label`, `conditioning_label`,
  `weekly_frequency_label`) pra exibição na ficha.

## 3. Conversão lead → aluno (serviço)
- `converter_contato_em_aluno(contato_id) -> Optional[int]` em `contatos/service.py`
  (direção de dependência contatos→alunos, sem ciclo: alunos não importa contatos).
  Lê o Contato; se None → None. Mapeia:
  - name ← nome; contact ← contato; sex ← sexo; age_reported ← idade;
  - objective ← objetivo; weekly_frequency ← frequencia_desejada;
  - conditioning_level ← nivel_condicionamento; restrictions ← lesoes;
  - health_conditions ← condicoes; medications ← medicamentos;
  - notes ← bloco curto e rotulado com o que não tem campo próprio: objetivos
    secundários, prazo desejado, e a observação do contato (quando houver), + "Criado
    a partir do cadastro em dd/mm/aaaa". status ← active.
  Cria via `create_aluno(...)` (reusa validação), depois marca o Contato como
  `status="virou_aluno"` (sai da caixa de novos contatos, fica no histórico).
  Retorna o id do novo Aluno.

## 4. Rota
- `POST /contatos/{id}/converter` (em `contatos/routes.py`): chama a conversão; 404 se
  a lead não existe; em sucesso `RedirectResponse` para `/alunos/{novo_id}` (abre a
  ficha do aluno recém-criado). (Não confundir com o `GET /contatos/{id}` do detalhe.)

## 5. Frontend
- **Detalhe da lead** (`contatos/lead_detalhe.html`): botão destacado "Transformar em
  aluno" (form POST → `/contatos/{id}/converter`). Uma frase curta: "Cria a ficha do
  aluno já com estes dados." (Se a lead já está "virou_aluno", pode ocultar/rotular.)
- **Formulário do aluno** (`alunos/_form.html`): novos campos em blocos (Dados gerais:
  contato, sexo, idade informada, frequência; Saúde: condições, medicamentos — lesões
  já existe como restrições; nível). Selects pras opções.
- **Ficha/perfil do aluno** (o template de perfil): exibir os novos campos (contato,
  sexo, nível, frequência, condições, medicamentos), com "sem registro" quando vazio.
- CSS: reusar componentes; sem cores novas.

## 6. Testes
- `test_aluno`/model: novas colunas; migração 0017 vira head (bumpar HEAD_REVISION em
  todos os `test_*_model.py` + `test_scaffold.py`; 0017 é ALTER em alunos, downgrade
  real no scaffold).
- Serviço alunos: create/update aceitam e validam os novos campos (sex/nível/freq
  inválidos → erro; age_reported fora de 1..120 → erro; vazios→None); `_to_dict` traz
  rótulos.
- `converter_contato_em_aluno`: cria o aluno com o mapeamento certo; marca a lead
  virou_aluno; id inexistente → None; objetivos secundários/prazo/observação vão pro
  notes.
- Rota `POST /contatos/{id}/converter`: cria e redireciona pra `/alunos/{id}`; 404 em
  id inexistente; depois a lead não aparece mais na lista de abertos.
- Ficha do aluno mostra os campos novos.
- Rodar a suíte inteira; reportar verde.

## Fora de escopo
- Editar/mesclar quando já existe um aluno com o mesmo nome (por ora sempre cria novo;
  detecção de duplicado fica pra depois).
- Modalidade (individual/grupo/digital) do plano — já vive no Financeiro (PlanoAluno);
  não dupĺicar aqui.

## Camadas / subagentes
banco-migracao-writer (0017 + colunas no Aluno) → servico-writer (alunos: campos +
validação + labels; contatos: converter_contato_em_aluno) → aplicacao-writer (rota
/converter + ajustes de contexto do perfil) → frontend-writer (botão no detalhe +
campos no _form + exibição no perfil) → teste-writer (suíte).
