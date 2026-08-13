"""Field-level encryption for secrets stored at rest (e.g. FHIR server auth_config).

Uses Fernet (symmetric, authenticated AES-128-CBC + HMAC) keyed from
FIELD_ENCRYPTION_KEY. Losing that key makes every encrypted value
permanently unrecoverable - back it up like any other production secret.
"""

import json

from cryptography.fernet import Fernet
from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings

_settings = get_settings()
_fernet = Fernet(_settings.FIELD_ENCRYPTION_KEY.encode())


def encrypt_json(value: dict) -> str:
    return _fernet.encrypt(json.dumps(value).encode()).decode()


def decrypt_json(token: str) -> dict:
    return json.loads(_fernet.decrypt(token.encode()).decode())


class EncryptedJSON(TypeDecorator):
    """A JSON column whose value is transparently encrypted at rest.

    The underlying DB column stays plain `json`: what's persisted is a
    single JSON string holding the Fernet ciphertext, so switching a
    column to this type only needs a data migration (re-encrypt existing
    plaintext dicts in place), not a column-type change.
    """

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_json(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt_json(value)
