"""
setup_sheets.py - Cria todas as abas e cabeçalhos no Google Sheets.

Uso:
    python sheets/setup_sheets.py

Requisitos:
    - .env com GOOGLE_SHEETS_ID e GOOGLE_CREDENTIALS_PATH configurados
    - Arquivo de credenciais OAuth2 do Google Cloud
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# Garante que o diretório raiz do projeto está no path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.google_client import get_sheets_client

load_dotenv(PROJECT_ROOT / ".env")

console = Console()

# Definição das abas e seus cabeçalhos
SHEET_TABS = {
    "Alunos": [
        "id", "nome", "idade", "sexo", "whatsapp", "email",
        "data_inicio", "plano", "frequencia_semanal", "status",
        "objetivo_principal", "observacoes",
    ],
    "Avaliacoes": [
        "id", "id_aluno", "nome_aluno", "data", "peso_kg",
        "percentual_gordura", "massa_magra_kg", "cintura_cm", "quadril_cm",
        "peito_cm", "braco_d_cm", "braco_e_cm", "coxa_d_cm", "coxa_e_cm",
        "observacoes",
    ],
    "Planos_Treino": [
        "id", "id_aluno", "nome_aluno", "nome_treino", "data_criacao",
        "fase", "objetivo_treino", "status",
    ],
    "Exercicios": [
        "id", "id_plano", "id_aluno", "grupo_muscular", "exercicio",
        "series", "repeticoes", "carga_kg", "descanso_seg", "observacoes",
    ],
    "Sessoes": [
        "id", "id_aluno", "nome_aluno", "data", "presente",
        "disposicao", "observacoes_sessao",
    ],
    "Follow_ups": [
        "id", "id_aluno", "nome_aluno", "data", "tipo",
        "texto_gerado", "status",
    ],
}


def get_existing_sheets(service, spreadsheet_id: str) -> dict[str, int]:
    """Retorna um dicionário {nome_aba: sheet_id} das abas existentes."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {
        sheet["properties"]["title"]: sheet["properties"]["sheetId"]
        for sheet in spreadsheet.get("sheets", [])
    }


def create_sheet_tab(service, spreadsheet_id: str, tab_name: str) -> int:
    """Cria uma nova aba na planilha e retorna seu sheetId."""
    body = {
        "requests": [
            {
                "addSheet": {
                    "properties": {"title": tab_name}
                }
            }
        ]
    }
    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body
    ).execute()
    new_sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]
    return new_sheet_id


def write_header_row(service, spreadsheet_id: str, tab_name: str, headers: list[str]) -> None:
    """Escreve o cabeçalho na primeira linha da aba."""
    range_notation = f"{tab_name}!A1:{chr(ord('A') + len(headers) - 1)}1"
    body = {
        "values": [headers]
    }
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_notation,
        valueInputOption="RAW",
        body=body,
    ).execute()


def format_header_row(service, spreadsheet_id: str, sheet_id: int, num_columns: int) -> None:
    """Aplica formatação de negrito e fundo cinza no cabeçalho."""
    body = {
        "requests": [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_columns,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.26, "green": 0.52, "blue": 0.96},
                            "textFormat": {
                                "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                                "bold": True,
                            },
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]
    }
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()


def setup_sheets() -> None:
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID")
    if not spreadsheet_id:
        console.print("[bold red]Erro:[/bold red] GOOGLE_SHEETS_ID não encontrado no .env")
        sys.exit(1)

    console.print("\n[bold blue]Sistema de Gestão de Alunos - Personal Trainer[/bold blue]")
    console.print("[dim]Configurando Google Sheets...[/dim]\n")

    service = get_sheets_client()
    existing_sheets = get_existing_sheets(service, spreadsheet_id)

    table = Table(title="Status das Abas", show_header=True, header_style="bold magenta")
    table.add_column("Aba", style="cyan", width=20)
    table.add_column("Status", width=15)
    table.add_column("Colunas", width=10)

    for tab_name, headers in SHEET_TABS.items():
        if tab_name in existing_sheets:
            sheet_id = existing_sheets[tab_name]
            status = "[yellow]Já existe[/yellow]"
        else:
            console.print(f"  Criando aba [cyan]{tab_name}[/cyan]...")
            sheet_id = create_sheet_tab(service, spreadsheet_id, tab_name)
            status = "[green]Criada[/green]"

        write_header_row(service, spreadsheet_id, tab_name, headers)
        format_header_row(service, spreadsheet_id, sheet_id, len(headers))
        table.add_row(tab_name, status, str(len(headers)))

    console.print(table)
    console.print("\n[bold green]Configuração concluída com sucesso![/bold green]")
    console.print(f"[dim]Planilha: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit[/dim]\n")


if __name__ == "__main__":
    setup_sheets()
