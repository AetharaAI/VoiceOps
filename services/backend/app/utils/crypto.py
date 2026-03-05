import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _derive_fernet_key(seed: str) -> bytes:
    digest = hashlib.sha256(seed.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def _get_cipher() -> Fernet:
    settings = get_settings()
    return Fernet(_derive_fernet_key(settings.tenant_secret_key))


def encrypt_secret(plaintext: str) -> str:
    return _get_cipher().encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt_secret(ciphertext: str) -> str:
    return _get_cipher().decrypt(ciphertext.encode('utf-8')).decode('utf-8')
