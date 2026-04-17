from cryptography.fernet import Fernet
from app.core.config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = get_settings().shopify_token_encryption_key
        if not key:
            raise ValueError("SHOPIFY_TOKEN_ENCRYPTION_KEY is not set")
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """Encrypt a Shopify access token before storing in DB."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a stored Shopify access token."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
