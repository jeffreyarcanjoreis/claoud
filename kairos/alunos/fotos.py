"""Storage for student photo uploads.

Receives raw bytes from the web layer and owns every rule about them: type
detection by magic bytes (never trusting the client's content-type), maximum
size, and the server-generated filename (architecture rule 6/10 — never trust
client-supplied names, never invent data). Functions here take and return
primitives only (bytes/str), so they are testable without FastAPI.
"""

import logging
import uuid
from typing import Optional

from kairos import config
from kairos.alunos.service import ValidationError

logger = logging.getLogger(__name__)

MAX_FOTO_BYTES = 5 * 1024 * 1024  # 5 MB

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _detect_image_ext(data: bytes) -> Optional[str]:
    """Detect the image type from its magic bytes.

    Returns "jpg", "png" or "webp" when the data starts with a recognized
    signature, or None otherwise. The client's declared content-type and
    filename are never trusted for this decision.
    """
    if data.startswith(_JPEG_MAGIC):
        return "jpg"
    if data.startswith(_PNG_MAGIC):
        return "png"
    if data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_foto(file_bytes: bytes, content_type: str, original_filename: str) -> str:
    """Validate and store an uploaded photo, returning its generated filename.

    ``content_type`` and ``original_filename`` are accepted only to keep the
    interface explicit about what an upload carries; neither is trusted for
    validation or for building the file path. The image type is detected
    from the actual bytes (magic numbers) and the filename saved to disk is
    always a server-generated ``uuid4().hex + "." + ext`` (defense against
    path traversal and extension spoofing).

    Raises :class:`ValidationError` (message in Portuguese, ready for
    display) when the file is empty, is not a recognized image type, or
    exceeds :data:`MAX_FOTO_BYTES`.
    """
    if not file_bytes:
        raise ValidationError("A foto está vazia.")

    ext = _detect_image_ext(file_bytes)
    if ext is None:
        raise ValidationError("A foto precisa ser uma imagem (JPG, PNG ou WEBP).")

    if len(file_bytes) > MAX_FOTO_BYTES:
        raise ValidationError("A foto é muito grande (máximo 5 MB).")

    name = f"{uuid.uuid4().hex}.{ext}"
    target_dir = config.fotos_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / name).write_bytes(file_bytes)

    logger.info("Foto saved: filename=%s bytes=%s", name, len(file_bytes))
    return name


def delete_foto_file(filename: Optional[str]) -> None:
    """Delete a previously saved photo file, if present.

    Does nothing when ``filename`` is falsy. As a defense against path
    traversal, also does nothing when ``filename`` is not a simple base
    name (contains "/", "\\" or ".."). Deleting a file that does not exist
    is not an error.
    """
    if not filename:
        return

    if "/" in filename or "\\" in filename or ".." in filename:
        logger.warning("Refusing to delete unsafe foto filename: %r", filename)
        return

    path = config.fotos_dir() / filename
    if path.exists():
        path.unlink()
        logger.info("Foto deleted: filename=%s", filename)
