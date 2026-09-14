"""Storage for exercise demonstration video uploads.

Receives raw bytes from the web layer and owns every rule about them: type
detection by magic bytes (never trusting the client's content-type), maximum
size, and the server-generated filename (architecture rule 6/10 — never trust
client-supplied names, never invent data). Functions here take and return
primitives only (bytes/str), so they are testable without FastAPI. Mirrors
:mod:`kairos.alunos.fotos`, applied to video files.
"""

import logging
import uuid
from typing import Optional

from kairos import config
from kairos.treinos.service import ValidationError

logger = logging.getLogger(__name__)

MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50 MB

_WEBM_MAGIC = b"\x1a\x45\xdf\xa3"


def _detect_video_ext(data: bytes) -> Optional[str]:
    """Detect the video type from its magic bytes.

    Returns "mp4", "webm" or "mov" when the data starts with a recognized
    signature, or None otherwise. The client's declared content-type and
    filename are never trusted for this decision.
    """
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand.startswith(b"qt"):
            return "mov"
        return "mp4"
    if data[4:8] == b"moov":
        return "mov"
    if data.startswith(_WEBM_MAGIC):
        return "webm"
    return None


def save_video(file_bytes: bytes, content_type: str, original_filename: str) -> str:
    """Validate and store an uploaded video, returning its generated filename.

    ``content_type`` and ``original_filename`` are accepted only to keep the
    interface explicit about what an upload carries; neither is trusted for
    validation or for building the file path. The video type is detected
    from the actual bytes (magic numbers) and the filename saved to disk is
    always a server-generated ``uuid4().hex + "." + ext`` (defense against
    path traversal and extension spoofing).

    Raises :class:`ValidationError` (message in Portuguese, ready for
    display) when the file is empty, is not a recognized video type, or
    exceeds :data:`MAX_VIDEO_BYTES`.
    """
    if not file_bytes:
        raise ValidationError("O vídeo está vazio.")

    ext = _detect_video_ext(file_bytes)
    if ext is None:
        raise ValidationError(
            "O vídeo precisa ser um arquivo de vídeo (MP4, WEBM ou MOV)."
        )

    if len(file_bytes) > MAX_VIDEO_BYTES:
        raise ValidationError("O vídeo é muito grande (máximo 50 MB).")

    name = f"{uuid.uuid4().hex}.{ext}"
    target_dir = config.videos_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / name).write_bytes(file_bytes)

    logger.info("Video saved: filename=%s bytes=%s", name, len(file_bytes))
    return name


def delete_video_file(filename: Optional[str]) -> None:
    """Delete a previously saved video file, if present.

    Does nothing when ``filename`` is falsy. As a defense against path
    traversal, also does nothing when ``filename`` is not a simple base
    name (contains "/", "\\" or ".."). Deleting a file that does not exist
    is not an error.
    """
    if not filename:
        return

    if "/" in filename or "\\" in filename or ".." in filename:
        logger.warning("Refusing to delete unsafe video filename: %r", filename)
        return

    path = config.videos_dir() / filename
    if path.exists():
        path.unlink()
        logger.info("Video deleted: filename=%s", filename)
