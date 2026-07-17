"""Future secret-storage seam; plaintext broker credentials are unsupported."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


class SecretStorageUnavailable(RuntimeError):
    """Raised instead of accepting a credential in this paper-only build."""


@dataclass(frozen=True)
class SecretReference:
    provider: str
    key: str


class SecretStore(Protocol):
    def store(self, key: str, value: str) -> SecretReference:
        """Store a secret with an external secret manager and return a reference."""

    def get(self, reference: SecretReference) -> Optional[str]:
        """Resolve a secret only at the approved runtime boundary."""


class DisabledSecretStore:
    """Safe default: reject secret collection rather than persist plaintext."""

    provider = 'disabled'

    def store(self, key: str, value: str) -> SecretReference:
        del key, value
        raise SecretStorageUnavailable(
            'Broker credential storage is disabled until an approved secret manager is configured.'
        )

    def get(self, reference: SecretReference) -> Optional[str]:
        del reference
        return None


broker_secret_store: SecretStore = DisabledSecretStore()
