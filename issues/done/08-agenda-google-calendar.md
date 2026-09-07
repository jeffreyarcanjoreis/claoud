# Agenda geral do coach — Google Calendar (só leitura, via iCal)

## Descrição
Mostrar no painel a agenda real do coach a partir do Google Calendar, lendo o endereço secreto no formato iCal (`.ics`) — só leitura, sem OAuth. A Agenda ganha separador próprio e um sub-nav com duas vistas à parte: "Sessões de hoje" (nossa base, intacta) e "Google Calendar" (próximos 14 dias, agrupado por dia).

## Decisões (com o PO)
- **Conexão:** URL secreto iCal (read-only), não OAuth completo (adiado para quando houver hospedagem).
- **Convivência:** nova vista "Google Calendar" à parte; a base de sessões Kairos fica intacta.

## Especificação funcional
- Camada de integração isolada lê o `.ics` por HTTP (timeout; `webcal://`→`https://`), faz parsing e expande recorrências numa janela de datas; devolve eventos normalizados ordenados cronologicamente.
- `GET /agenda/google`: sem `KAIROS_GCAL_ICS_URL` → estado de configuração (passo-a-passo); com URL → eventos dos próximos 14 dias agrupados por dia (hora ou "dia inteiro", título, local); feed vazio → estado vazio; falha de leitura → 502 amigável. Nunca inventa eventos (rule 6).
- A URL secreta vem só do ambiente e nunca é registada.
- Separador "Agenda" na navegação + sub-nav nas duas vistas.
- 273 testes anteriores continuam verdes.

## Arquivos criados
- `kairos/agenda/gcal.py` — integração: `fetch_events`/`parse_events`, `GcalEvent`, `GcalError`/`GcalNotConfigured`; `icalendar` + `recurring-ical-events`.
- `kairos/templates/painel/agenda_google.html` — vista com os estados (config/ok/erro/vazio).
- `kairos/templates/painel/_agenda_subnav.html` — sub-nav partilhado.
- `tests/test_agenda_google.py` — 13 testes (parsing/recorrência/dia-inteiro/fuso/vazio/malformado/não-configurado + rota nos 4 estados + navegação).

## Arquivos modificados
- `kairos/config.py` — `gcal_ics_url()` (env `KAIROS_GCAL_ICS_URL`).
- `kairos/painel/routes.py` — rota `/agenda/google` (agrupamento por dia, rótulos PT) + `subtab` na `/agenda`.
- `kairos/templates/base.html` — separador "Agenda".
- `kairos/templates/painel/agenda.html` — inclui o sub-nav.
- `kairos/static/css/components.css` — estilos da agenda geral.
- `pyproject.toml` — deps `icalendar>=7.0`, `recurring-ical-events>=3.0`.

## Camadas envolvidas
configuração, integração (gcal), aplicação (rota), frontend (templates+css), teste

## Validação
286 testes verdes. Browser (feed local de ponta a ponta): recorrência semanal expandida (seg/qua/sex), horas/locais e rótulos de dia em PT; estado de configuração confirmado sem URL.

## Status
concluída
