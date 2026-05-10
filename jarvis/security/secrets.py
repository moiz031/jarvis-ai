# secrets.py - Secure secrets management for Jarvis

import os
import base64
import uuid
import logging

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.fernet import Fernet
except Exception:
    hashes = PBKDF2HMAC = Fernet = None

logger = logging.getLogger(__name__)

class SecretsManager:
    """Manages encryption and decryption of sensitive environment variables."""
    
    def __init__(self):
        self.key = self._generate_key()
        self.fernet = Fernet(self.key) if (Fernet is not None and self.key) else None
        if self.fernet is None:
            logger.warning(
                "cryptography is unavailable. Secret encryption is disabled until the dependency is installed."
            )
        
    def _generate_key(self):
        """Generate a machine-specific key using hardware UUID."""
        if hashes is None or PBKDF2HMAC is None:
            return None
        # Get machine UUID (unique to the hardware)
        machine_id = str(uuid.getnode())
        salt = b'jarvis_secure_salt_2025' # Fixed salt for consistency across restarts
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
        return key

    def encrypt(self, value):
        """Encrypt a string value."""
        if not value:
            return value
        if self.fernet is None:
            logger.warning("Skipping secret encryption because cryptography is unavailable.")
            return value
        encrypted = self.fernet.encrypt(value.encode()).decode()
        return f"ENC:{encrypted}"

    def decrypt(self, encrypted_value):
        """Decrypt a value if it starts with 'ENC:' prefix."""
        if not isinstance(encrypted_value, str) or not encrypted_value.startswith("ENC:"):
            return encrypted_value
        if self.fernet is None:
            logger.warning("Cannot decrypt encrypted secret without cryptography. Returning None.")
            return None
        
        try:
            token = encrypted_value[4:] # Remove 'ENC:'
            decrypted = self.fernet.decrypt(token.encode()).decode()
            return decrypted
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            return None

# Global instance
secrets_manager = SecretsManager()

if __name__ == "__main__":
    # Utility to encrypt values from command line if needed
    import sys
    if len(sys.argv) > 1:
        val = sys.argv[1]
        print(f"Original: {val}")
        print(f"Encrypted: {secrets_manager.encrypt(val)}")
