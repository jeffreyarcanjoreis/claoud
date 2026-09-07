"""Integration layer: reads and interprets a student's Excel folder.

Opens every ``.xlsx`` of a folder in read-only mode (the coach's original files
are never modified), looks for the labels ``atleta``, ``idade``, ``periodo`` and
``objetivo`` in the first column of every sheet, and returns what it recognized
plus an honest report of what it could NOT import.

Architecture rule 6 (data is never invented) drives every decision here: a value
that cannot be read with confidence does not become a field, it becomes an entry
in ``not_imported`` or ``warnings``. Architecture rule 10: code and identifiers
in English, coach-facing text in Portuguese.

This module never touches the database and never prints anything.
"""

import datetime
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openpyxl import load_workbook

logger = logging.getLogger(__name__)

#: Labels recognized in the first column of each sheet, already normalized.
LABEL_NAME = "atleta"
LABEL_AGE = "idade"
LABEL_PERIOD = "periodo"
LABEL_OBJECTIVE = "objetivo"

KNOWN_LABELS = (LABEL_NAME, LABEL_AGE, LABEL_PERIOD, LABEL_OBJECTIVE)

#: Dates as the coach types them: DD/MM/AAAA, possibly with garbage around.
DATE_PATTERN = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")

#: Slices that do not exist in the system yet; always reported as not imported.
FUTURE_SLICES = (
    "macrociclo, mesociclo e semanas",
    "observações",
    "plano de treino (split semanal força/cardio)",
    "dieta (refeições e macros)",
)

FUTURE_SLICE_REASON = "fatia futura — ainda não existe no sistema"

AGE_REASON = (
    "o sistema guarda data de nascimento, e derivar uma data a partir da idade "
    "seria inventar dado"
)


@dataclass
class ParsedImport:
    """Everything read from a student's Excel folder.

    Attributes:
        fields: Recognized fields ready for the service layer. Possible keys:
            ``name``, ``objective``, ``plan_start``, ``plan_end`` (dates already
            in ISO "YYYY-MM-DD").
        not_imported: Pairs of (item, reason), both in Portuguese.
        warnings: Portuguese messages about divergences and partial readings.
        source_files: Names of the ``.xlsx`` files actually read, in the order
            they were read (alphabetical).
    """

    fields: Dict[str, str] = field(default_factory=dict)
    not_imported: List[Tuple[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)


def normalize_label(value: object) -> str:
    """Normalize a cell so labels compare regardless of accents/case/spacing.

    Removes accents (NFKD), lowercases, strips, collapses inner whitespace and
    drops a trailing ":".
    """
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    if text.endswith(":"):
        text = text[:-1].strip()
    return text


def _cell_text(value: object) -> str:
    """Return a cell's text, formatting dates/datetimes the way Excel shows them."""
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, datetime.date):
        return value.strftime("%d/%m/%Y")
    return str(value).strip()


def _collapse_spaces(text: str) -> str:
    """Collapse repeated inner whitespace and strip the ends."""
    return re.sub(r"\s+", " ", text).strip()


def extract_dates(text: str) -> List[str]:
    """Extract every DD/MM/AAAA date from *text* and return them in ISO order found.

    Tolerates garbage between the dates ("inicio :02/01/2024 ?termino 15/02/2024").
    Impossible dates (e.g. 32/13/2024) are skipped instead of being guessed.
    """
    dates: List[str] = []
    for raw in DATE_PATTERN.findall(text):
        day, month, year = (int(part) for part in raw.split("/"))
        try:
            dates.append(datetime.date(year, month, day).isoformat())
        except ValueError:
            continue
    return dates


def _iter_label_values(path: Path):
    """Yield (label, raw_value_text) for every recognized label in a workbook.

    The workbook is opened strictly read-only, so the coach's original file is
    never touched. Labels are searched by name in column A of every sheet — never
    by row index, since the real files place them on different rows.
    """
    workbook = load_workbook(path, data_only=True, read_only=True)
    try:
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                if not row:
                    continue
                label = normalize_label(row[0].value)
                if label not in KNOWN_LABELS:
                    continue
                value = ""
                for cell in row[1:]:
                    text = _cell_text(cell.value)
                    if text:
                        value = text
                        break
                yield label, value
    finally:
        workbook.close()


def _read_folder(folder: Path, result: ParsedImport) -> Dict[str, str]:
    """Read every .xlsx of *folder*, returning the first value found per label.

    Divergences (same label, different value in another file/sheet) are recorded
    as warnings; the first value always wins.
    """
    files = sorted(
        (p for p in folder.iterdir()
         if p.is_file()
         and p.suffix.lower() == ".xlsx"
         and not p.name.startswith("~$")),
        key=lambda p: p.name.lower(),
    )
    if not files:
        raise FileNotFoundError(f"Nenhum arquivo .xlsx encontrado em {folder}")

    values: Dict[str, str] = {}
    origins: Dict[str, str] = {}

    for path in files:
        result.source_files.append(path.name)
        try:
            pairs = list(_iter_label_values(path))
        except Exception as exc:  # noqa: BLE001 - never swallow silently (rule 8)
            logger.warning("Falha ao ler a planilha %s: %s", path.name, exc)
            result.warnings.append(
                f'Não foi possível ler o arquivo "{path.name}": {exc}'
            )
            continue

        for label, value in pairs:
            if not value:
                continue
            if label not in values:
                values[label] = value
                origins[label] = path.name
                continue
            if _collapse_spaces(values[label]) != _collapse_spaces(value):
                result.warnings.append(
                    f'Divergência no campo "{label}": foi usado '
                    f'"{values[label]}" (de {origins[label]}) e ignorado '
                    f'"{value}" (de {path.name}).'
                )

    return values


def _apply_period(raw: Optional[str], result: ParsedImport) -> None:
    """Turn the raw "periodo" text into plan_start/plan_end, or report the failure."""
    if raw is None:
        return
    dates = extract_dates(raw)
    if not dates:
        result.not_imported.append(
            (
                "período",
                "nenhuma data no formato DD/MM/AAAA foi reconhecida no texto "
                f'original "{raw}"',
            )
        )
        return
    result.fields["plan_start"] = dates[0]
    if len(dates) >= 2:
        result.fields["plan_end"] = dates[1]
    else:
        result.warnings.append(
            f'Apenas uma data foi encontrada no período ("{raw}"): ela foi usada '
            "como início do plano e o término ficou sem registro."
        )
    if len(dates) > 2:
        result.warnings.append(
            f'Mais de duas datas foram encontradas no período ("{raw}"): foram '
            "usadas as duas primeiras."
        )


def parse_aluno_folder(folder) -> ParsedImport:
    """Read a student's Excel folder and return what could be interpreted.

    Args:
        folder: Path (or string) of the folder holding the student's ``.xlsx``
            files.

    Returns:
        A :class:`ParsedImport` with the recognized fields, the items that were
        not imported (with the reason, in Portuguese), the warnings and the file
        names read.

    Raises:
        FileNotFoundError: When the folder does not exist, is not a folder, or
            holds no ``.xlsx`` file.
    """
    path = Path(folder)
    if not path.exists():
        raise FileNotFoundError(f"Pasta não encontrada: {path}")
    if not path.is_dir():
        raise FileNotFoundError(f"O caminho informado não é uma pasta: {path}")

    result = ParsedImport()
    values = _read_folder(path, result)

    name = values.get(LABEL_NAME)
    if name:
        # Only collapse repeated spaces: no recapitalization, no spell fixing.
        result.fields["name"] = _collapse_spaces(name)

    objective = values.get(LABEL_OBJECTIVE)
    if objective:
        result.fields["objective"] = objective.strip()

    _apply_period(values.get(LABEL_PERIOD), result)

    age = values.get(LABEL_AGE)
    if age:
        result.not_imported.append((f'idade "{age}"', AGE_REASON))

    for item in FUTURE_SLICES:
        result.not_imported.append((item, FUTURE_SLICE_REASON))

    logger.info(
        "Planilhas lidas em %s: %s campo(s) reconhecido(s), %s item(ns) não importado(s)",
        path,
        len(result.fields),
        len(result.not_imported),
    )
    return result
