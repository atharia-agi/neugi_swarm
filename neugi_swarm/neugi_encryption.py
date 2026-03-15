#!/usr/bin/env python3
"""
🤖 NEUGI ENCRYPTION
=====================

Encryption utilities:
- File encryption/decryption
- Password hashing
- Secure storage
- Key management

Version: 1.0
Date: March 16, 2026
"""

import os
import hashlib
import base64
import json
import secrets
from typing import Optional, Tuple
from datetime import datetime
from pathlib import Path

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
    from cryptography.hazmat.backends import default_backend

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("Install cryptography: pip install cryptography")

NEUGI_DIR = os.path.expanduser("~/neugi")
KEYS_DIR = os.path.join(NEUGI_DIR, "keys")
os.makedirs(KEYS_DIR, exist_ok=True)


class Encryption:
    """Encryption utilities"""

    @staticmethod
    def generate_key(password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
        """Generate encryption key from password"""
        if not CRYPTO_AVAILABLE:
            return None, None

        if salt is None:
            salt = secrets.token_bytes(16)

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt

    @staticmethod
    def encrypt(data: str, key: bytes) -> str:
        """Encrypt data"""
        if not CRYPTO_AVAILABLE:
            return None

        f = Fernet(key)
        encrypted = f.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    @staticmethod
    def decrypt(encrypted_data: str, key: bytes) -> Optional[str]:
        """Decrypt data"""
        if not CRYPTO_AVAILABLE:
            return None

        try:
            f = Fernet(key)
            decrypted = f.decrypt(base64.urlsafe_b64decode(encrypted_data))
            return decrypted.decode()
        except Exception:
            return None

    @staticmethod
    def hash_password(password: str, salt: bytes = None) -> Tuple[str, bytes]:
        """Hash password"""
        if salt is None:
            salt = secrets.token_bytes(32)

        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)

        return base64.b64encode(hashed).decode(), salt

    @staticmethod
    def verify_password(password: str, hashed: str, salt: bytes) -> bool:
        """Verify password"""
        new_hash, _ = Encryption.hash_password(password, salt)
        return new_hash == hashed

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate secure token"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def hash_string(text: str, algorithm: str = "sha256") -> str:
        """Hash string"""
        if algorithm == "sha256":
            return hashlib.sha256(text.encode()).hexdigest()
        elif algorithm == "sha512":
            return hashlib.sha512(text.encode()).hexdigest()
        elif algorithm == "md5":
            return hashlib.md5(text.encode()).hexdigest()
        return hashlib.sha256(text.encode()).hexdigest()


class SecureStorage:
    """Secure encrypted storage"""

    def __init__(self, storage_file: str = None):
        self.storage_file = storage_file or os.path.join(KEYS_DIR, "secure_storage.json")
        self.key = None
        self._load_or_create_key()

    def _load_or_create_key(self):
        """Load or create encryption key"""
        key_file = os.path.join(KEYS_DIR, ".master.key")

        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key() if CRYPTO_AVAILABLE else secrets.token_bytes(32)
            with open(key_file, "wb") as f:
                f.write(self.key)
            os.chmod(key_file, 0o600)

    def store(self, key: str, value: str):
        """Store encrypted value"""
        if not CRYPTO_AVAILABLE:
            return

        data = {}
        if os.path.exists(self.storage_file):
            with open(self.storage_file, "r") as f:
                try:
                    data = json.load(f)
                except:
                    data = {}

        encrypted = Encryption.encrypt(value, self.key)
        data[key] = {"encrypted": encrypted, "timestamp": datetime.now().isoformat()}

        with open(self.storage_file, "w") as f:
            json.dump(data, f, indent=2)

    def retrieve(self, key: str) -> Optional[str]:
        """Retrieve encrypted value"""
        if not CRYPTO_AVAILABLE:
            return None

        if not os.path.exists(self.storage_file):
            return None

        with open(self.storage_file, "r") as f:
            try:
                data = json.load(f)
            except:
                return None

        if key not in data:
            return None

        return Encryption.decrypt(data[key]["encrypted"], self.key)

    def delete(self, key: str):
        """Delete stored value"""
        if not os.path.exists(self.storage_file):
            return

        with open(self.storage_file, "r") as f:
            try:
                data = json.load(f)
            except:
                return

        if key in data:
            del data[key]

            with open(self.storage_file, "w") as f:
                json.dump(data, f, indent=2)

    def list_keys(self) -> list:
        """List stored keys"""
        if not os.path.exists(self.storage_file):
            return []

        with open(self.storage_file, "r") as f:
            try:
                data = json.load(f)
                return list(data.keys())
            except:
                return []


class KeyManager:
    """Manage encryption keys"""

    def __init__(self):
        self.keys_dir = KEYS_DIR

    def create_key(self, name: str, password: str = None) -> Dict:
        """Create new encryption key"""
        if not CRYPTO_AVAILABLE:
            return {"error": "Cryptography not installed"}

        key_file = os.path.join(self.keys_dir, f"{name}.key")

        if os.path.exists(key_file):
            return {"error": "Key already exists"}

        if password:
            key, salt = Encryption.generate_key(password)
        else:
            key = Fernet.generate_key()
            salt = None

        with open(key_file, "wb") as f:
            f.write(key)
        os.chmod(key_file, 0o600)

        metadata = {
            "name": name,
            "created": datetime.now().isoformat(),
            "password_protected": password is not None,
            "salt": base64.b64encode(salt).decode() if salt else None,
        }

        meta_file = os.path.join(self.keys_dir, f"{name}.meta")
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2)

        return {"success": True, "name": name}

    def list_keys(self) -> List[Dict]:
        """List all keys"""
        keys = []

        for f in os.listdir(self.keys_dir):
            if f.endswith(".meta"):
                name = f[:-5]
                with open(os.path.join(self.keys_dir, f)) as fp:
                    meta = json.load(fp)
                    keys.append(
                        {
                            "name": name,
                            "created": meta.get("created"),
                            "password_protected": meta.get("password_protected", False),
                        }
                    )

        return keys

    def delete_key(self, name: str) -> Dict:
        """Delete key"""
        key_file = os.path.join(self.keys_dir, f"{name}.key")
        meta_file = os.path.join(self.keys_dir, f"{name}.meta")

        if not os.path.exists(key_file):
            return {"error": "Key not found"}

        os.remove(key_file)
        if os.path.exists(meta_file):
            os.remove(meta_file)

        return {"success": True}


class FileEncryptor:
    """Encrypt/decrypt files"""

    @staticmethod
    def encrypt_file(input_file: str, output_file: str = None, key: bytes = None) -> Dict:
        """Encrypt file"""
        if not CRYPTO_AVAILABLE:
            return {"error": "Cryptography not installed"}

        if key is None:
            key = Fernet.generate_key()

        if output_file is None:
            output_file = input_file + ".enc"

        try:
            with open(input_file, "rb") as f:
                data = f.read()

            f = Fernet(key)
            encrypted = f.encrypt(data)

            with open(output_file, "wb") as f:
                f.write(encrypted)

            return {"success": True, "output_file": output_file, "key": key.decode()}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def decrypt_file(input_file: str, output_file: str = None, key: str = None) -> Dict:
        """Decrypt file"""
        if not CRYPTO_AVAILABLE:
            return {"error": "Cryptography not installed"}

        try:
            with open(input_file, "rb") as f:
                encrypted = f.read()

            f = Fernet(key.encode())
            decrypted = f.decrypt(encrypted)

            if output_file is None:
                output_file = input_file.replace(".enc", ".dec")

            with open(output_file, "wb") as f:
                f.write(decrypted)

            return {"success": True, "output_file": output_file}
        except Exception as e:
            return {"error": str(e)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Encryption")
    parser.add_argument("--encrypt-file", type=str, help="Encrypt file")
    parser.add_argument("--decrypt-file", type=str, help="Decrypt file")
    parser.add_argument("--key", type=str, help="Encryption key")
    parser.add_argument("--hash", type=str, help="Hash string")
    parser.add_argument("--generate-key", action="store_true", help="Generate new key")
    parser.add_argument("--list-keys", action="store_true", help="List keys")
    parser.add_argument("--secure-store", nargs=2, help="Store: KEY VALUE")
    parser.add_argument("--secure-get", type=str, help="Retrieve: KEY")

    args = parser.parse_args()

    if args.generate_key:
        key = Fernet.generate_key() if CRYPTO_AVAILABLE else None
        print(f"Generated key: {key.decode() if key else 'Install cryptography'}")

    elif args.hash:
        print(f"SHA256: {Encryption.hash_string(args.hash)}")

    elif args.encrypt_file:
        result = FileEncryptor.encrypt_file(
            args.encrypt_file, key=args.key.encode() if args.key else None
        )
        if result.get("success"):
            print(f"Encrypted: {result['output_file']}")
            print(f"Key: {result['key']}")
        else:
            print(f"Error: {result.get('error')}")

    elif args.decrypt_file:
        result = FileEncryptor.decrypt_file(args.decrypt_file, key=args.key)
        if result.get("success"):
            print(f"Decrypted: {result['output_file']}")
        else:
            print(f"Error: {result.get('error')}")

    elif args.list_keys:
        km = KeyManager()
        keys = km.list_keys()
        print("\n📁 Keys:")
        for k in keys:
            print(f"   {k['name']} (created: {k['created']})")

    elif args.secure_store:
        storage = SecureStorage()
        storage.store(args.secure_store[0], args.secure_store[1])
        print(f"Stored: {args.secure_store[0]}")

    elif args.secure_get:
        storage = SecureStorage()
        value = storage.retrieve(args.secure_get)
        print(f"Value: {value}")

    else:
        print("NEUGI Encryption Tools")
        print(
            "Usage: python -m neugi_encryption [--encrypt-file FILE] [--hash STRING] [--generate-key] [--list-keys]"
        )


if __name__ == "__main__":
    main()
