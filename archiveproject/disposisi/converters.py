import base64
import hashlib

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from django.conf import settings


ASSOCIATED_DATA = [b"pwu-disposisi-url-v1"]


def _cipher():
    """Build a deterministic authenticated cipher from Django's secret key."""
    key = hashlib.sha512(
        f"disposisi-url:{settings.SECRET_KEY}".encode()
    ).digest()
    return AESSIV(key)


class EncryptedDisposisiIdConverter:
    regex = r"[-A-Za-z0-9_=]+"

    def to_python(self, value):
        try:
            ciphertext = base64.urlsafe_b64decode(value.encode())
            plaintext = _cipher().decrypt(
                ciphertext,
                ASSOCIATED_DATA,
            ).decode()
            pk = int(plaintext)
        except (
            InvalidTag,
            UnicodeDecodeError,
            ValueError,
            OverflowError,
        ):
            raise ValueError
        if pk < 1:
            raise ValueError
        return pk

    def to_url(self, value):
        try:
            pk = int(value)
        except (TypeError, ValueError):
            raise ValueError
        if pk < 1:
            raise ValueError
        ciphertext = _cipher().encrypt(
            str(pk).encode(),
            ASSOCIATED_DATA,
        )
        return base64.urlsafe_b64encode(ciphertext).decode()
