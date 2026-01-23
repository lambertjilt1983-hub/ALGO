import os
from cryptography.fernet import Fernet
import bcrypt

class EncryptionManager:
    """Handles encryption/decryption of sensitive data"""
    
    def __init__(self):
        key = os.getenv("FERNET_KEY")

        if not key:
            raise RuntimeError("FERNET_KEY is missing in environment variables")

        try:
            if isinstance(key, str):
                key = key.encode()
            self.cipher = Fernet(key)
        except Exception as e:
            raise RuntimeError("Invalid FERNET_KEY format") from e
    
    def encrypt_credentials(self, plaintext: str) -> str:
        """Encrypt sensitive credentials"""
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt_credentials(self, encrypted: str) -> str:
        """Decrypt sensitive credentials"""
        return self.cipher.decrypt(encrypted.encode()).decode()
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        # Limit password to 72 bytes for bcrypt
        pwd = password.encode()[:72]
        salt = bcrypt.gensalt(rounds=10)
        return bcrypt.hashpw(pwd, salt).decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        # Limit password to 72 bytes for bcrypt
        pwd = plain_password.encode()[:72]
        return bcrypt.checkpw(pwd, hashed_password.encode('utf-8'))

encryption_manager = EncryptionManager()
