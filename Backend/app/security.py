import os
from dotenv import load_dotenv # <-- IMPORT ADDED
from cryptography.fernet import Fernet
from app.config import get_logger

load_dotenv() 

logger = get_logger(__name__)

# Now, os.getenv will successfully find the key you pasted in the .env file!
_env_key = os.getenv("ENCRYPTION_KEY")
if not _env_key:
    raise ValueError("CRITICAL ERROR: ENCRYPTION_KEY environment variable is not set. Cannot start server securely.")

cipher = Fernet(_env_key.encode())
MASK = "••••••••••••••••••••••••••••••••"

def encrypt_key(plain_text: str) -> str:
    if not plain_text or plain_text == MASK:
        return plain_text
    try:
        # Prevent double encryption
        cipher.decrypt(plain_text.encode())
        return plain_text
    except Exception:
        return cipher.encrypt(plain_text.encode()).decode()

def decrypt_key(cipher_text: str) -> str:
    if not cipher_text or cipher_text == MASK:
        return ""
    try:
        return cipher.decrypt(cipher_text.encode()).decode()
    except Exception:
        return cipher_text # Fallback if it was saved as plaintext previously