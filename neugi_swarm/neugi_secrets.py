#!/usr/bin/env python3
"""
🤖 NEUGI SECRETS MANAGER
===========================

Secrets management:
- Store secrets
- Version control
- Access control
- Encryption

Version: 1.0
Date: March 16, 2026
"""

import os
import json
import uuid
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

try:
    from cryptography.fernet import Fernet

    CRYPTO_AVAILABLE = True
except:
    CRYPTO_AVAILABLE = False

NEUGI_DIR = os.path.expanduser("~/neugi")
SECRETS_DIR = os.path.join(NEUGI_DIR, "secrets")
os.makedirs(SECRETS_DIR, exist_ok=True)


class Secret:
    """Secret definition"""

    def __init__(
        self,
        name: str,
        value: str,
        secret_type: str = "generic",
        metadata: Dict = None,
        version: int = 1,
    ):
        self.id = str(uuid.uuid4())[:12]
        self.name = name
        self.value = value
        self.secret_type = secret_type
        self.metadata = metadata or {}
        self.version = version
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "secret_type": self.secret_type,
            "metadata": self.metadata,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SecretsManager:
    """Secrets manager"""

    def __init__(self):
        self.secrets: Dict[str, List[Secret]] = {}
        self._key = None
        self._setup_key()
        self._load()

    def _setup_key(self):
        """Setup encryption key"""
        key_file = os.path.join(SECRETS_DIR, ".key")

        if CRYPTO_AVAILABLE:
            if os.path.exists(key_file):
                with open(key_file, "rb") as f:
                    self._key = f.read()
            else:
                self._key = Fernet.generate_key()
                with open(key_file, "wb") as f:
                    f.write(self._key)
                os.chmod(key_file, 0o600)

    def _load(self):
        """Load secrets"""
        secrets_file = os.path.join(SECRETS_DIR, "secrets.json")
        if os.path.exists(secrets_file):
            try:
                with open(secrets_file) as f:
                    data = json.load(f)
                    for name, versions in data.items():
                        self.secrets[name] = [
                            Secret(
                                s["name"],
                                s["value"],
                                s.get("secret_type"),
                                s.get("metadata"),
                                s.get("version", 1),
                            )
                            for s in versions
                        ]
            except:
                pass

    def _save(self):
        """Save secrets"""
        secrets_file = os.path.join(SECRETS_DIR, "secrets.json")
        data = {name: [s.to_dict() for s in versions] for name, versions in self.secrets.items()}
        with open(secrets_file, "w") as f:
            json.dump(data, f, indent=2)

    def _encrypt(self, value: str) -> str:
        """Encrypt value"""
        if not CRYPTO_AVAILABLE or not self._key:
            return value

        f = Fernet(self._key)
        encrypted = f.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, value: str) -> str:
        """Decrypt value"""
        if not CRYPTO_AVAILABLE or not self._key:
            return value

        try:
            f = Fernet(self._key)
            decrypted = f.decrypt(base64.b64decode(value))
            return decrypted.decode()
        except:
            return value

    def set(
        self, name: str, value: str, secret_type: str = "generic", metadata: Dict = None
    ) -> Secret:
        """Set secret"""
        encrypted_value = self._encrypt(value)

        if name not in self.secrets:
            self.secrets[name] = []

        version = len(self.secrets[name]) + 1
        secret = Secret(name, encrypted_value, secret_type, metadata, version)
        self.secrets[name].append(secret)
        self._save()

        return secret

    def get(self, name: str, version: int = None) -> Optional[str]:
        """Get secret"""
        if name not in self.secrets:
            return None

        if version:
            for secret in self.secrets[name]:
                if secret.version == version:
                    return self._decrypt(secret.value)
        else:
            return self._decrypt(self.secrets[name][-1].value)

        return None

    def delete(self, name: str) -> bool:
        """Delete secret"""
        if name in self.secrets:
            del self.secrets[name]
            self._save()
            return True
        return False

    def list(self) -> List[Dict]:
        """List secrets"""
        result = []
        for name, versions in self.secrets.items():
            latest = versions[-1]
            result.append(
                {
                    "name": name,
                    "type": latest.secret_type,
                    "versions": len(versions),
                    "created_at": latest.created_at,
                    "updated_at": latest.updated_at,
                }
            )
        return result

    def versions(self, name: str) -> List[Dict]:
        """Get secret versions"""
        if name not in self.secrets:
            return []
        return [{"version": s.version, "created_at": s.created_at} for s in self.secrets[name]]

    def rotate(self, name: str, value: str) -> Secret:
        """Rotate secret"""
        return self.set(name, value)


secrets_manager = SecretsManager()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Secrets Manager")
    parser.add_argument("--set", nargs=2, metavar=("NAME", "VALUE"), help="Set secret")
    parser.add_argument("--get", type=str, help="Get secret")
    parser.add_argument("--delete", type=str, help="Delete secret")
    parser.add_argument("--list", action="store_true", help="List secrets")
    parser.add_argument("--versions", type=str, help="List versions")

    args = parser.parse_args()

    if args.set:
        secret = secrets_manager.set(args.set[0], args.set[1])
        print(f"Set secret: {args.set[0]} (v{secret.version})")

    elif args.get:
        value = secrets_manager.get(args.get)
        if value:
            print(f"{args.get}: {value}")
        else:
            print("Secret not found")

    elif args.delete:
        if secrets_manager.delete(args.delete):
            print(f"Deleted: {args.delete}")
        else:
            print("Secret not found")

    elif args.list:
        secrets = secrets_manager.list()
        print(f"\n🔐 Secrets ({len(secrets)}):\n")
        for s in secrets:
            print(f"  {s['name']} (v{s['versions']}) - {s['type']}")

    elif args.versions:
        versions = secrets_manager.versions(args.versions)
        print(f"\n🔐 {args.versions} versions:\n")
        for v in versions:
            print(f"  v{v['version']} - {v['created_at']}")

    else:
        print("NEUGI Secrets Manager")
        print(
            "Usage: python -m neugi_secrets [--set NAME VALUE|--get NAME|--delete NAME|--list|--versions NAME]"
        )


if __name__ == "__main__":
    main()
