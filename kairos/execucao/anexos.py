"""Storage for student execution attachments (photo or video).

Receives raw bytes from the web layer and owns every rule about them: type
detection by magic bytes (never trusting the client's content-type), maximum
size, and the server-generated filename (architecture rule 6/10). Accepts an
image (JPG, PNG, WEBP) or a video (MP4, WEBM, MOV). Functions here take and
return primitives only, so they are testable without FastAPI. Mirrors
:mod:`kairos.alunos.fotos` and :mod:`kairos.treinos.videos`.
"""

import logging
import uuid
from typing import Optional, Tuple

from kairos import config
from kairos.treinos.service import ValidationError

logger = logging.getLogger(__name__)

MAX_ANEXO_BYTES = 50 * 1024 * 1024  # 50 MB

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_WEBM_MAGIC = b"\x1a\x45\xdf\xa3"


def _detect_anexo(data: bytes) -> Optional[Tuple[str, str]]:
    """Detect the attachment type from its magic bytes.

    Returns ``(ext, tipo)`` where ``tipo`` is "imagem" or "video", or None
    when the signature is not recognized. The client's declared content-type
    and filename are never trusted for this decision.
    """
    if data.startswith(_JPEG_MAGIC):
        return ("jpg", "imagem")
    if data.startswith(_PNG_MAGIC):
        return ("png", "imagem")
    if data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ("webp", "imagem")

    if data[4:8] == b"ftyp":
        if data[8:12].startswith(b"qt"):
            return ("mov", "video")
        return ("mp4", "video")
    if data[4:8] == b"moov":
        return ("mov", "video")
    if data.startswith(_WEBM_MAGIC):
        return ("webm", "video")
    return None


def save_anexo(
    file_bytes: bytes, content_type: str, original_filename: str
) -> Tuple[str, str]:
    """Validate and store an uploaded attachment, returning ``(filename, tipo)``.

    ``content_type`` and ``original_filename`` are never trusted. The type is
    detected from the actual bytes and the stored name is always a
    server-generated ``uuid4().hex + "." + ext``.

    Raises :class:`ValidationError` (Portuguese message) when the file is
    empty, not a recognized image/video, or larger than
    :data:`MAX_ANEXO_BYTES`.
    """
    if not file_bytes:
        raise ValidationError("O anexo está vazio.")

    detected = _detect_anexo(file_bytes)
    if detected is None:
        raise ValidationError(
            "O anexo precisa ser uma imagem (JPG, PNG, WEBP) ou vídeo "
            "(MP4, WEBM, MOV)."
        )

    if len(file_bytes) > MAX_ANEXO_BYTES:
        raise ValidationError("O anexo é muito grande (máximo 50 MB).")

    ext, tipo = detected
    name = f"{uuid.uuid4().hex}.{ext}"
    target_dir = config.anexos_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / name).write_bytes(file_bytes)

    logger.info(
        "Anexo saved: filename=%s tipo=%s bytes=%s", name, tipo, len(file_bytes)
    )
    return name, tipo


def delete_anexo_file(filename: Optional[str]) -> None:
    """Delete a previously saved attachment file, if present.

    Does nothing when ``filename`` is falsy or not a simple base name
    (contains "/", "\\" or ".."; logged as a warning). Deleting a file that
    does not exist is not an error.
    """
    if not filename:
        return

    if "/" in filename or "\\" in filename or ".." in filename:
        logger.warning("Refusing to delete unsafe anexo filename: %r", filename)
        return

    path = config.anexos_dir() / filename
    if path.exists():
        path.unlink()
        logger.info("Anexo deleted: filename=%s", filename)
