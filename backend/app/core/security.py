from cryptography.fernet import Fernet
from app.core.config import get_settings
import bcrypt

class EncryptionManager:
    """Handles encryption/decryption of sensitive data"""
    
    def __init__(self):
        settings = get_settings()
        # Use a consistent key from settings
        import base64
        key = settings.ENCRYPTION_KEY.encode()
        # Ensure it's a valid Fernet key (32 bytes, base64 encoded)
        if len(key) < 32:
            key = (key + b'0' * 32)[:32]
        # Convert to valid base64 Fernet key
        fernet_key = base64.urlsafe_b64encode(key)
        self.cipher = Fernet(fernet_key)
    
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
