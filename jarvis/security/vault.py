
import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class SecurityVault:
    def __init__(self, vault_dir="data/vault"):
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.key_file = self.vault_dir / "vault.key"
        self.fernet = None
        
    def _generate_key(self, password: str, salt: bytes = None):
        """Generate a key from password using KDF."""
        if not salt:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt

    def setup_vault(self, password: str):
        """Initialize the vault with a master password."""
        key, salt = self._generate_key(password)
        self.fernet = Fernet(key)
        
        # Save salt (and potentially a verification token)
        with open(self.key_file, "wb") as f:
            f.write(salt)
            
        print("Vault initialized.")

    def unlock_vault(self, password: str) -> bool:
        """Unlock the vault using password."""
        if not self.key_file.exists():
            print("Vault not set up.")
            return False
            
        try:
            with open(self.key_file, "rb") as f:
                salt = f.read(16)
                
            key, _ = self._generate_key(password, salt)
            self.fernet = Fernet(key)
            # Verify? For now assume correct if no error
            return True
        except Exception as e:
            print(f"Unlock failed: {e}")
            return False

    def encrypt_file(self, file_path: str):
        if not self.fernet: raise Exception("Vault locked")
        
        path = Path(file_path)
        with open(path, "rb") as f:
            data = f.read()
            
        encrypted = self.fernet.encrypt(data)
        
        with open(path.with_suffix(path.suffix + ".enc"), "wb") as f:
            f.write(encrypted)
            
    def decrypt_file(self, enc_path: str):
        if not self.fernet: raise Exception("Vault locked")
        
        path = Path(enc_path)
        with open(path, "rb") as f:
            data = f.read()
            
        decrypted = self.fernet.decrypt(data)
        
        original_name = path.with_suffix("").name # Remove .enc? No, complex.
        # Just writing to .dec for now or return bytes
        return decrypted

# Example Usage
if __name__ == "__main__":
    v = SecurityVault(vault_dir="jarvis/data/vault")
    # v.setup_vault("mypassword")
    # v.unlock_vault("mypassword")
