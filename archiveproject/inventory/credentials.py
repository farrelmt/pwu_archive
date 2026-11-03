"""Encrypt software account passwords before writing them to the database."""

import base64
import hashlib

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings


def _fernet():
    keys = [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
    return MultiFernet([
        Fernet(base64.urlsafe_b64encode(hashlib.sha256(
            f"inventory-software-password:v1:{key}".encode()
        ).digest()))
        for key in keys
    ])


def encrypt_software_password(password):
    return _fernet().encrypt(password.encode()).decode() if password else None


def decrypt_software_password(ciphertext):
    return _fernet().decrypt(ciphertext.encode()).decode() if ciphertext else None
