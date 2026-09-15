"""Signed, time-limited activation tokens that bind a student id.

Used by the `/ativar/<token>` link sent to a student. The token is not a
session credential: it only proves that its holder was given the link and
that the link has not expired, then unlocks a one-time activation flow tied
to a specific `aluno_id`.
"""

from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from kairos import config

# Fixed salt: scopes this serializer to activation tokens only, so a token
# generated here can never be replayed as valid input for some other future
# use of the same application secret.
_SALT = "ativacao-aluno"

# Link validity window: 7 days.
MAX_AGE_SEGUNDOS = 7 * 24 * 60 * 60


def _serializer() -> URLSafeTimedSerializer:
    """Build the serializer on demand (never at import time).

    Building it lazily means the current value of `config.secret_key()` is
    always used, which keeps this working correctly under tests that patch
    the secret via environment variables or monkeypatching.
    """
    return URLSafeTimedSerializer(config.secret_key(), salt=_SALT)


def gerar_token_ativacao(aluno_id: int) -> str:
    """Serialize `aluno_id` into a signed, timestamped activation token."""
    return _serializer().dumps(aluno_id)


def ler_token_ativacao(token: str, max_age: int = MAX_AGE_SEGUNDOS) -> Optional[int]:
    """Recover the `aluno_id` embedded in an activation token.

    Tolerant read: returns `None` for any expired, tampered, malformed, or
    otherwise unreadable token instead of raising, since this is meant to be
    called on untrusted input straight from a URL. Never logs (this is a
    validation read, not a write).
    """
    try:
        payload = _serializer().loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature, TypeError, ValueError):
        return None
    if not isinstance(payload, int):
        return None
    return payload
