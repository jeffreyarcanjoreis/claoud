# Arco da sessão — coach (definir duração + arco visível)

## Descrição
Na planilha do coach, o coach define a duração da sessão (30/45/60 ou limpar) e vê o arco das 5 fases com os minutos proporcionais. Comportamentos [F1] 1 (UI) e 3.

## Depende de
13 (dados + serviço: `set_duracao`, `arco_da_sessao`, `duracao_min`)

## Status
concluída

## Especificação funcional
Só UI + rota do coach; a regra está no serviço da 13. O componente de arco (faixa das 5 fases proporcional ao tempo) nasce aqui e é reusado read-only na 15.

- **Rota (coach, `kairos/treinos/routes.py`):**
  - `POST /alunos/{aluno_id}/treino/{treino_id}/duracao` (form `duracao`): gate de coach padrão (aluno existe; treino do aluno → 404); `set_duracao(treino_id, duracao)`; em `ValidationError` no-op/reexibir conforme padrão do arquivo; 303 de volta à planilha.
  - **Detalhe do coach:** o contexto do template passa a incluir `arco = arco_da_sessao(treino_id)` (lista de 5 fases com minutos, ou None) e `duracao_min` atual + `DURACAO_OPCOES` para o seletor.
- **Template (`kairos/templates/treinos/aluno_detalhe.html`):**
  - No topo (perto da apresentação), um **seletor de duração**: botões/opções 30 / 45 / 60 (forms POST com `duracao=30|45|60`), com a atual destacada, e uma opção de **limpar** (`duracao=""`).
  - Quando houver `arco`, o **componente de arco**: as 5 fases como segmentos horizontais de largura proporcional aos `minutos` (ex.: `flex: {{ f.minutos }}`), cada segmento com o rótulo da fase, a pergunta-guia e os minutos. Sem duração → sem arco, só o convite a definir a duração.
- **CSS (`components.css`):** faixa do arco (segmentos flex proporcionais; cor por fase ou um gradiente discreto no tom do tema; minutos legíveis), seletor de duração (chips, a atual destacada). Responsivo (empilhar/enc%olher em telas estreitas). Só tokens existentes.

Casos de borda: sem duração → nenhum arco, convite discreto; duração adulterada → no-op; ao trocar a duração, o arco reflete os novos minutos.

## Pré-condições
- Fatia 13 concluída. Head 0032 (sem schema novo aqui).

## Arquivos a modificar
- `kairos/treinos/routes.py` — rota POST duração + arco/duração no contexto do detalhe do coach.
- `kairos/templates/treinos/aluno_detalhe.html` — seletor de duração + componente de arco.
- `kairos/static/css/components.css` — arco + seletor.

## Camadas envolvidas
- **aplicação** (`aplicacao-writer`): rota de duração + enriquecer o detalhe do coach.
- **frontend** (`frontend-writer`): seletor + componente de arco + CSS.
- **testes** (`teste-writer`): `tests/test_treino_arco_coach.py` — POST duração grava e a planilha mostra o arco com os minutos certos e a duração destacada; limpar remove o arco; duração adulterada → no-op; treino de outro aluno → 404; sem duração → sem arco, com convite. Suíte completa verde (head 0032).
