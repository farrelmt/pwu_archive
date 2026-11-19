"""Opaque, stable URL identifiers for risk records."""

import base64
import hashlib

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from django.conf import settings


class EncryptedRiskIdConverter:
    regex = "[A-Za-z0-9_-]+"
    _context = b"risk-url-v1"

    @classmethod
    def _cipher(cls, secret):
        key = hashlib.sha512(cls._context + b":" + secret.encode()).digest()
        return AESSIV(key)

    def to_url(self, value):
        risk_id = int(value)
        if risk_id < 1:
            raise ValueError("Invalid risk ID")
        encrypted = self._cipher(settings.SECRET_KEY).encrypt(
            risk_id.to_bytes(8, "big"), [self._context],
        )
        return base64.urlsafe_b64encode(encrypted).decode().rstrip("=")

    def to_python(self, value):
        try:
            encrypted = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
            for secret in (settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS):
                try:
                    plaintext = self._cipher(secret).decrypt(encrypted, [self._context])
                except (InvalidTag, ValueError):
                    continue
                if len(plaintext) == 8:
                    risk_id = int.from_bytes(plaintext, "big")
                    if risk_id > 0:
                        return risk_id
        except (ValueError, TypeError):
            pass
        raise ValueError("Invalid encrypted risk ID")
