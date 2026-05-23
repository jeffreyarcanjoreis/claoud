"""
generate_report.py - Gera relatórios e follow-ups para alunos usando Claude AI.

Uso:
    python scripts/generate_report.py --aluno "João Silva" --tipo relatorio
    python scripts/generate_report.py --aluno ALU001 --tipo followup
    python scripts/generate_report.py --aluno "Maria" --tipo treino

Tipos disponíveis:
    relatorio  - Relatório completo de progresso (avaliações, treino, aderência ao objetivo)
    followup   - Mensagem personalizada para enviar ao aluno
    treino     - Revisão do plano de treino com sugestões baseadas na evolução
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

# Garante que o diretório raiz do projeto está no path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

import anthropic
from scripts.google_client import (
    get_sheets_client,
    get_drive_client,
    read_sheet_tab,
    write_to_drive,
)

console = Console()

SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_ID")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_VAULT_FOLDER_ID")
MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Busca de dados
# ---------------------------------------------------------------------------

def find_student(identifier: str) -> dict | None:
    """
    Localiza um aluno pelo nome (busca parcial, case-insensitive) ou pelo ID exato.

    Args:
        identifier: Nome ou ID do aluno.

    Returns:
        Dicionário com os dados do aluno ou None se não encontrado.
    """
    alunos = read_sheet_tab(SPREADSHEET_ID, "Alunos")
    identifier_lower = identifier.strip().lower()

    # Busca por ID exato primeiro
    for aluno in alunos:
        if aluno.get("id", "").lower() == identifier_lower:
            return aluno

    # Busca por nome (parcial, case-insensitive)
    matches = [a for a in alunos if identifier_lower in a.get("nome", "").lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        console.print(
            f"[yellow]Atenção:[/yellow] Múltiplos alunos encontrados para '[bold]{identifier}[/bold]':"
        )
        for m in matches:
            console.print(f"  - [{m['id']}] {m['nome']}")
        console.print("Use o ID exato para identificar o aluno.")
        return None

    return None


def fetch_student_data(aluno_id: str, nome_aluno: str) -> dict:
    """
    Busca todos os dados relacionados ao aluno nas abas do Sheets.

    Args:
        aluno_id: ID do aluno (ex: ALU001).
        nome_aluno: Nome do aluno para mensagens de log.

    Returns:
        Dicionário com listas de avaliacoes, planos, exercicios e sessoes.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Carregando dados do Google Sheets...", total=None)

        # Avaliações
        progress.update(task, description="Lendo avaliações...")
        all_avaliacoes = read_sheet_tab(SPREADSHEET_ID, "Avaliacoes")
        avaliacoes = [a for a in all_avaliacoes if a.get("id_aluno") == aluno_id]

        # Planos de treino
        progress.update(task, description="Lendo planos de treino...")
        all_planos = read_sheet_tab(SPREADSHEET_ID, "Planos_Treino")
        planos = [p for p in all_planos if p.get("id_aluno") == aluno_id]

        # Exercícios dos planos do aluno
        progress.update(task, description="Lendo exercícios...")
        plano_ids = {p["id"] for p in planos}
        all_exercicios = read_sheet_tab(SPREADSHEET_ID, "Exercicios")
        exercicios = [e for e in all_exercicios if e.get("id_plano") in plano_ids]

        # Sessões
        progress.update(task, description="Lendo sessões...")
        all_sessoes = read_sheet_tab(SPREADSHEET_ID, "Sessoes")
        sessoes = [s for s in all_sessoes if s.get("id_aluno") == aluno_id]

        progress.update(task, description="Dados carregados!")

    return {
        "avaliacoes": sorted(avaliacoes, key=lambda x: x.get("data", "")),
        "planos": sorted(planos, key=lambda x: x.get("data_criacao", ""), reverse=True),
        "exercicios": exercicios,
        "sessoes": sorted(sessoes, key=lambda x: x.get("data", "")),
    }


# ---------------------------------------------------------------------------
# Construção do prompt
# ---------------------------------------------------------------------------

def _format_avaliacoes(avaliacoes: list[dict]) -> str:
    if not avaliacoes:
        return "Nenhuma avaliação registrada."
    lines = []
    for av in avaliacoes:
        lines.append(
            f"  [{av.get('data', 'S/D')}] "
            f"Peso: {av.get('peso_kg', '?')}kg | "
            f"% Gordura: {av.get('percentual_gordura', '?')}% | "
            f"Massa Magra: {av.get('massa_magra_kg', '?')}kg | "
            f"Cintura: {av.get('cintura_cm', '?')}cm | "
            f"Quadril: {av.get('quadril_cm', '?')}cm | "
            f"Peito: {av.get('peito_cm', '?')}cm | "
            f"Braço D: {av.get('braco_d_cm', '?')}cm | "
            f"Braço E: {av.get('braco_e_cm', '?')}cm | "
            f"Coxa D: {av.get('coxa_d_cm', '?')}cm | "
            f"Coxa E: {av.get('coxa_e_cm', '?')}cm"
        )
        if av.get("observacoes"):
            lines.append(f"    Obs: {av['observacoes']}")
    return "\n".join(lines)


def _format_planos_e_exercicios(planos: list[dict], exercicios: list[dict]) -> str:
    if not planos:
        return "Nenhum plano de treino registrado."
    lines = []
    for plano in planos:
        status_tag = "ATIVO" if plano.get("status") == "ativo" else "arquivado"
        lines.append(
            f"  [{plano.get('data_criacao', 'S/D')}] [{status_tag}] "
            f"{plano.get('nome_treino', '?')} — Fase: {plano.get('fase', '?')} "
            f"| Objetivo: {plano.get('objetivo_treino', '?')}"
        )
        plano_exercicios = [e for e in exercicios if e.get("id_plano") == plano.get("id")]
        if plano_exercicios:
            for ex in plano_exercicios:
                lines.append(
                    f"    • [{ex.get('grupo_muscular', '?')}] {ex.get('exercicio', '?')}: "
                    f"{ex.get('series', '?')}x{ex.get('repeticoes', '?')} @ "
                    f"{ex.get('carga_kg', '?')}kg | Descanso: {ex.get('descanso_seg', '?')}s"
                )
                if ex.get("observacoes"):
                    lines.append(f"      Obs: {ex['observacoes']}")
    return "\n".join(lines)


def _format_sessoes(sessoes: list[dict]) -> str:
    if not sessoes:
        return "Nenhuma sessão registrada."
    total = len(sessoes)
    presencas = sum(1 for s in sessoes if s.get("presente", "").lower() == "sim")
    ausencias = total - presencas
    taxa = round(presencas / total * 100) if total > 0 else 0

    disposicoes = [
        int(s["disposicao"]) for s in sessoes
        if s.get("disposicao") and str(s["disposicao"]).isdigit()
    ]
    media_disp = round(sum(disposicoes) / len(disposicoes), 1) if disposicoes else "N/A"

    ultimas = sessoes[-5:] if len(sessoes) >= 5 else sessoes
    detalhes = []
    for s in reversed(ultimas):
        detalhes.append(
            f"  [{s.get('data', 'S/D')}] "
            f"{'Presente' if s.get('presente','').lower()=='sim' else 'Ausente'} | "
            f"Disposição: {s.get('disposicao', '?')}/5"
            + (f" | {s['observacoes_sessao']}" if s.get("observacoes_sessao") else "")
        )
    return (
        f"  Total de sessões: {total} | Presenças: {presencas} | "
        f"Ausências: {ausencias} | Taxa de comparecimento: {taxa}%\n"
        f"  Disposição média: {media_disp}/5\n"
        f"  Últimas sessões:\n" + "\n".join(detalhes)
    )


def build_prompt(aluno: dict, dados: dict, tipo: str) -> str:
    """
    Constrói o prompt estruturado para o Claude com todos os dados do aluno.

    Args:
        aluno: Dicionário com os dados cadastrais do aluno.
        dados: Dicionário com avaliacoes, planos, exercicios e sessoes.
        tipo: Tipo de geração ('relatorio', 'followup', 'treino').

    Returns:
        String com o prompt completo.
    """
    hoje = date.today().isoformat()

    instrucoes = {
        "relatorio": (
            "Gere um RELATÓRIO COMPLETO DE PROGRESSO para o personal trainer. "
            "O relatório deve: (1) comparar as avaliações ao longo do tempo destacando "
            "evoluções e pontos de atenção em cada métrica corporal; (2) analisar a evolução "
            "dos planos de treino e progressão de cargas; (3) avaliar a aderência ao objetivo "
            "principal; (4) analisar a frequência e disposição nas sessões; (5) concluir com "
            "recomendações objetivas para as próximas semanas. Seja detalhado, técnico e "
            "use linguagem profissional. Formate em Markdown com seções claras."
        ),
        "followup": (
            "Escreva uma MENSAGEM PERSONALIZADA DE FOLLOW-UP que o personal trainer pode "
            "enviar diretamente ao aluno via WhatsApp ou e-mail. A mensagem deve: ser calorosa "
            "e motivadora; mencionar conquistas específicas observadas nos dados; abordar pontos "
            "de melhoria com encorajamento; perguntar sobre como o aluno está se sentindo; "
            "reforçar o objetivo principal. Tom: informal, empático, profissional. "
            "Máximo 300 palavras. Formate como texto corrido, não use headers Markdown."
        ),
        "treino": (
            "Gere uma REVISÃO DO PLANO DE TREINO com sugestões baseadas na evolução do aluno. "
            "A revisão deve: (1) avaliar o plano atual em relação ao objetivo; (2) analisar a "
            "progressão de cargas e volume; (3) identificar grupos musculares sub ou super "
            "trabalhados; (4) sugerir ajustes específicos de exercícios, séries, repetições e "
            "cargas; (5) recomendar a próxima fase/periodização. Seja específico com números. "
            "Formate em Markdown com tabelas quando relevante."
        ),
    }

    prompt = f"""Você é um assistente especializado em análise de desempenho para personal trainers.
Data de hoje: {hoje}

=== DADOS DO ALUNO ===
Nome: {aluno.get('nome', '?')}
ID: {aluno.get('id', '?')}
Idade: {aluno.get('idade', '?')} anos
Sexo: {aluno.get('sexo', '?')}
Data de início: {aluno.get('data_inicio', '?')}
Plano: {aluno.get('plano', '?')}
Frequência semanal: {aluno.get('frequencia_semanal', '?')}x por semana
Status: {aluno.get('status', '?')}
Objetivo principal: {aluno.get('objetivo_principal', '?')}
Observações gerais: {aluno.get('observacoes', 'Nenhuma')}

=== HISTÓRICO DE AVALIAÇÕES ({len(dados['avaliacoes'])} registros) ===
{_format_avaliacoes(dados['avaliacoes'])}

=== PLANOS DE TREINO E EXERCÍCIOS ({len(dados['planos'])} planos) ===
{_format_planos_e_exercicios(dados['planos'], dados['exercicios'])}

=== HISTÓRICO DE SESSÕES ({len(dados['sessoes'])} sessões) ===
{_format_sessoes(dados['sessoes'])}

=== TAREFA ===
{instrucoes[tipo]}
"""
    return prompt


# ---------------------------------------------------------------------------
# Geração com Claude
# ---------------------------------------------------------------------------

def generate_with_claude(prompt: str, tipo: str) -> str:
    """
    Envia o prompt para o Claude e retorna o conteúdo gerado.

    Args:
        prompt: Prompt completo com dados do aluno e instrução.
        tipo: Tipo de geração para exibição no log.

    Returns:
        Texto gerado pelo Claude.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[bold red]Erro:[/bold red] ANTHROPIC_API_KEY não encontrado no .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    tipo_labels = {
        "relatorio": "Relatório de Progresso",
        "followup": "Mensagem de Follow-up",
        "treino": "Revisão do Plano de Treino",
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(
            f"Gerando {tipo_labels.get(tipo, tipo)} com Claude...", total=None
        )
        message = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

    return message.content[0].text


# ---------------------------------------------------------------------------
# Formatação Markdown com frontmatter Obsidian
# ---------------------------------------------------------------------------

def build_markdown(aluno: dict, conteudo: str, tipo: str) -> str:
    """
    Envolve o conteúdo gerado em um arquivo Markdown com frontmatter Obsidian.

    Args:
        aluno: Dados do aluno para o frontmatter.
        conteudo: Texto gerado pelo Claude.
        tipo: Tipo de documento para tags e título.

    Returns:
        String Markdown completa com frontmatter.
    """
    hoje = date.today().isoformat()

    tipo_info = {
        "relatorio": {
            "tag": "relatorio",
            "titulo": "Relatório de Progresso",
            "emoji": "📊",
        },
        "followup": {
            "tag": "followup",
            "titulo": "Follow-up",
            "emoji": "💬",
        },
        "treino": {
            "tag": "revisao-treino",
            "titulo": "Revisão do Plano de Treino",
            "emoji": "🏋️",
        },
    }

    info = tipo_info.get(tipo, {"tag": tipo, "titulo": tipo.capitalize(), "emoji": "📄"})
    nome = aluno.get("nome", "Aluno")
    objetivo = aluno.get("objetivo_principal", "")

    frontmatter = f"""---
title: "{info['titulo']} — {nome}"
date: {hoje}
aluno: "{nome}"
id_aluno: "{aluno.get('id', '')}"
tipo: {info['tag']}
objetivo: "{objetivo}"
tags:
  - personal-trainer
  - aluno
  - {info['tag']}
gerado_por: claude-sonnet-4-6
---
"""

    header = f"# {info['emoji']} {info['titulo']} — {nome}\n\n> **Data:** {hoje}  \n> **Objetivo:** {objetivo}\n\n---\n\n"

    return frontmatter + header + conteudo


# ---------------------------------------------------------------------------
# Salvamento no Google Drive
# ---------------------------------------------------------------------------

def save_to_drive(aluno: dict, markdown_content: str, tipo: str) -> str:
    """
    Salva o arquivo Markdown no Google Drive e registra o follow-up no Sheets.

    Args:
        aluno: Dados do aluno.
        markdown_content: Conteúdo Markdown gerado.
        tipo: Tipo do documento.

    Returns:
        URL do arquivo no Google Drive.
    """
    folder_id = os.getenv("GOOGLE_DRIVE_VAULT_FOLDER_ID")
    if not folder_id:
        console.print("[yellow]Aviso:[/yellow] GOOGLE_DRIVE_VAULT_FOLDER_ID não configurado. Pulando upload.")
        return ""

    hoje = date.today().isoformat()
    nome_slug = aluno.get("nome", "aluno").lower().replace(" ", "_")
    # Remove caracteres especiais do nome do arquivo
    import re
    nome_slug = re.sub(r"[^a-z0-9_]", "", nome_slug.replace("ã", "a").replace("ç", "c")
                       .replace("é", "e").replace("ê", "e").replace("á", "a")
                       .replace("â", "a").replace("í", "i").replace("ó", "o")
                       .replace("ô", "o").replace("ú", "u").replace("õ", "o"))
    filename = f"{nome_slug}_{tipo}_{hoje}.md"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Salvando '{filename}' no Google Drive...", total=None)
        url = write_to_drive(folder_id, filename, markdown_content)

    # Registra o follow-up gerado na aba Follow_ups
    if tipo == "followup":
        _register_followup(aluno, markdown_content, hoje)

    return url


def _register_followup(aluno: dict, conteudo: str, data: str) -> None:
    """Registra o follow-up gerado na aba Follow_ups do Sheets."""
    try:
        service = get_sheets_client()
        # Gera um ID simples baseado em timestamp
        import time
        fup_id = f"FUP{int(time.time())}"
        nova_linha = [
            fup_id,
            aluno.get("id", ""),
            aluno.get("nome", ""),
            data,
            "mensagem",
            conteudo[:1000],  # Trunca para não exceder o limite da célula
            "pendente",
        ]
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Follow_ups!A:G",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [nova_linha]},
        ).execute()
    except Exception as exc:
        console.print(f"[yellow]Aviso:[/yellow] Não foi possível registrar follow-up no Sheets: {exc}")


# ---------------------------------------------------------------------------
# CLI principal
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gerador de relatórios e follow-ups para Personal Trainer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/generate_report.py --aluno "João Silva" --tipo relatorio
  python scripts/generate_report.py --aluno ALU001 --tipo followup
  python scripts/generate_report.py --aluno "Maria" --tipo treino
        """,
    )
    parser.add_argument(
        "--aluno",
        required=True,
        help="Nome (parcial) ou ID do aluno (ex: ALU001)",
    )
    parser.add_argument(
        "--tipo",
        required=True,
        choices=["relatorio", "followup", "treino"],
        help="Tipo de geração: relatorio | followup | treino",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    console.print(
        Panel.fit(
            "[bold blue]Sistema de Gestão de Alunos[/bold blue]\n"
            "[dim]Personal Trainer × Claude AI × Google Workspace[/dim]",
            border_style="blue",
        )
    )

    # Valida configuração
    if not SPREADSHEET_ID:
        console.print("[bold red]Erro:[/bold red] GOOGLE_SHEETS_ID não encontrado no .env")
        sys.exit(1)

    # Localiza o aluno
    console.print(f"\n[bold]Buscando aluno:[/bold] {args.aluno}")
    aluno = find_student(args.aluno)
    if not aluno:
        console.print(f"[bold red]Erro:[/bold red] Aluno '{args.aluno}' não encontrado na planilha.")
        sys.exit(1)

    # Exibe dados do aluno encontrado
    info_table = Table(show_header=False, box=None, padding=(0, 1))
    info_table.add_column("Campo", style="dim")
    info_table.add_column("Valor", style="bold")
    info_table.add_row("Nome", aluno.get("nome", "?"))
    info_table.add_row("ID", aluno.get("id", "?"))
    info_table.add_row("Objetivo", aluno.get("objetivo_principal", "?"))
    info_table.add_row("Status", aluno.get("status", "?"))
    console.print(info_table)

    # Busca dados
    console.print()
    dados = fetch_student_data(aluno["id"], aluno["nome"])

    # Exibe resumo dos dados encontrados
    resumo = Table(title="Dados carregados", show_header=True, header_style="bold cyan")
    resumo.add_column("Categoria")
    resumo.add_column("Registros", justify="right")
    resumo.add_row("Avaliações", str(len(dados["avaliacoes"])))
    resumo.add_row("Planos de Treino", str(len(dados["planos"])))
    resumo.add_row("Exercícios", str(len(dados["exercicios"])))
    resumo.add_row("Sessões", str(len(dados["sessoes"])))
    console.print(resumo)
    console.print()

    # Gera prompt e chama Claude
    prompt = build_prompt(aluno, dados, args.tipo)
    conteudo = generate_with_claude(prompt, args.tipo)

    # Monta Markdown com frontmatter Obsidian
    markdown = build_markdown(aluno, conteudo, args.tipo)

    # Salva no Google Drive
    url = save_to_drive(aluno, markdown, args.tipo)

    # Resultado final
    console.print()
    console.print(
        Panel(
            f"[bold green]Geração concluída com sucesso![/bold green]\n\n"
            f"[bold]Aluno:[/bold] {aluno.get('nome')}\n"
            f"[bold]Tipo:[/bold] {args.tipo}\n"
            + (f"[bold]Drive:[/bold] {url}" if url else "[dim]Arquivo não salvo no Drive (variável não configurada).[/dim]"),
            title="Resultado",
            border_style="green",
        )
    )

    # Imprime o conteúdo gerado no terminal
    console.print("\n[bold dim]--- Conteúdo gerado ---[/bold dim]\n")
    console.print(conteudo)


if __name__ == "__main__":
    main()
