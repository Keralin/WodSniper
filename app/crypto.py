"""Encryption utilities for sensitive data."""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_encryption_key() -> bytes:
    """
    Derive encryption key from SECRET_KEY.

    Uses PBKDF2 to derive a Fernet-compatible key from the app's SECRET_KEY.
    """
    secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    salt = b'wodsniper_credential_salt'  # Static salt (key rotation not needed for this use case)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
    return key


def encrypt_credential(plaintext: str) -> str:
    """
    Encrypt a credential string.

    Args:
        plaintext: The credential to encrypt

    Returns:
        Base64-encoded encrypted string
    """
    if not plaintext:
        return None

    key = _get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(plaintext.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_credential(encrypted: str) -> str:
    """
    Decrypt a credential string.

    Args:
        encrypted: Base64-encoded encrypted string

    Returns:
        Decrypted plaintext string
    """
    if not encrypted:
        return None

    try:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted.encode())
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception:
        return None
