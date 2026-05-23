"""
google_client.py - Inicializa e expõe clientes autenticados para as APIs do Google.

Módulo auxiliar usado por outros scripts do sistema. Gerencia autenticação OAuth2
e provê funções de alto nível para leitura de Sheets e escrita no Drive.
"""

import io
import os
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

load_dotenv(Path(__file__).parent.parent / ".env")

# Escopos necessários para Sheets (leitura/escrita) e Drive (upload de arquivos)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Cache dos clientes para evitar autenticações repetidas na mesma sessão
_sheets_client = None
_drive_client = None


def _get_credentials() -> Credentials:
    """
    Obtém credenciais OAuth2 válidas.
    - Carrega token salvo de token.json se existir e for válido.
    - Renova automaticamente com refresh_token se expirado.
    - Abre fluxo de autorização no navegador se necessário.
    """
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    token_path = Path(credentials_path).parent / "token.json"

    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(credentials_path).exists():
                raise FileNotFoundError(
                    f"Arquivo de credenciais não encontrado: {credentials_path}\n"
                    "Faça o download em: Google Cloud Console > APIs & Services > Credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)

        # Salva o token para reutilização nas próximas execuções
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def get_sheets_client():
    """Retorna um cliente autenticado para a API do Google Sheets (v4)."""
    global _sheets_client
    if _sheets_client is None:
        creds = _get_credentials()
        _sheets_client = build("sheets", "v4", credentials=creds)
    return _sheets_client


def get_drive_client():
    """Retorna um cliente autenticado para a API do Google Drive (v3)."""
    global _drive_client
    if _drive_client is None:
        creds = _get_credentials()
        _drive_client = build("drive", "v3", credentials=creds)
    return _drive_client


def read_sheet_tab(spreadsheet_id: str, tab_name: str) -> list[dict]:
    """
    Lê todos os dados de uma aba do Google Sheets.

    Retorna uma lista de dicionários onde cada chave é o cabeçalho da coluna
    e cada valor é o dado da célula correspondente.

    Args:
        spreadsheet_id: ID da planilha do Google Sheets.
        tab_name: Nome da aba (ex: "Alunos", "Avaliacoes").

    Returns:
        Lista de dicts com os dados de cada linha, ou lista vazia se a aba
        estiver vazia ou só tiver cabeçalho.
    """
    service = get_sheets_client()
    range_notation = f"{tab_name}!A:ZZ"

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_notation)
        .execute()
    )

    values = result.get("values", [])
    if len(values) < 2:
        return []

    headers = values[0]
    rows = []
    for row in values[1:]:
        # Preenche células vazias no final da linha com string vazia
        padded_row = row + [""] * (len(headers) - len(row))
        rows.append(dict(zip(headers, padded_row)))

    return rows


def write_to_drive(folder_id: str, filename: str, content: str) -> str:
    """
    Faz upload de um arquivo de texto (Markdown) para uma pasta no Google Drive.

    Se já existir um arquivo com o mesmo nome na pasta, ele será atualizado
    em vez de criar um duplicado.

    Args:
        folder_id: ID da pasta de destino no Google Drive.
        filename: Nome do arquivo (ex: "joao_relatorio_2024-01-15.md").
        content: Conteúdo do arquivo em texto plano / Markdown.

    Returns:
        URL web do arquivo criado/atualizado no Google Drive.
    """
    service = get_drive_client()

    # Verifica se já existe um arquivo com esse nome na pasta
    query = (
        f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    )
    existing = service.files().list(q=query, fields="files(id, name)").execute()
    existing_files = existing.get("files", [])

    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")),
        mimetype="text/markdown",
        resumable=False,
    )

    if existing_files:
        # Atualiza o arquivo existente
        file_id = existing_files[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        # Cria novo arquivo
        file_metadata = {
            "name": filename,
            "parents": [folder_id],
            "mimeType": "text/markdown",
        }
        result = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
        ).execute()
        file_id = result["id"]

    # Garante que o arquivo tenha permissão de leitura para quem tiver o link
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    file_info = service.files().get(fileId=file_id, fields="webViewLink").execute()
    return file_info.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
