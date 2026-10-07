from datetime import datetime, timedelta

from cryptography.fernet import Fernet

from core.errors import MissingCredentials
from core.models import Secret, expiry_within
from core.timeutil import utcnow


class MemoryVault:
    def __init__(self, key: str):
        if not key:
            raise MissingCredentials("VAULT_FERNET_KEY")
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        self.rows: dict[str, dict] = {}

    def put(self, name: str, plaintext: str, expires_at: str | None = None) -> None:
        self.rows[name] = {
            "ciphertext": self._fernet.encrypt(plaintext.encode()).decode(),
            "expires_at": expires_at,
        }

    def get(self, name: str) -> str:
        return self._fernet.decrypt(self.rows[name]["ciphertext"].encode()).decode()

    def expiring(self, now: datetime | None = None, days: int = 7) -> list[tuple[str, str]]:
        now = now or utcnow()
        found = []
        for name, row in self.rows.items():
            if expiry_within(row.get("expires_at"), now, days):
                found.append((name, row["expires_at"]))
        return found


class SqlVault:
    def __init__(self, session, key: str):
        if not key:
            raise MissingCredentials("VAULT_FERNET_KEY")
        self.session = session
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def put(self, name: str, plaintext: str, expires_at: str | None = None) -> None:
        ciphertext = self._fernet.encrypt(plaintext.encode()).decode()
        row = self.session.query(Secret).filter_by(name=name).one_or_none()
        if row is None:
            row = Secret(name=name, ciphertext=ciphertext, expires_at=expires_at)
            self.session.add(row)
        else:
            row.ciphertext = ciphertext
            row.expires_at = expires_at
        self.session.commit()

    def get(self, name: str) -> str:
        row = self.session.query(Secret).filter_by(name=name).one()
        return self._fernet.decrypt(row.ciphertext.encode()).decode()

    def expiring(self, now: datetime | None = None, days: int = 7) -> list[tuple[str, str]]:
        now = now or utcnow()
        found = []
        for row in self.session.query(Secret).all():
            if expiry_within(row.expires_at, now, days):
                found.append((row.name, row.expires_at))
        return found


def alert_expiring_credentials(vault, queue, now: datetime | None = None) -> list[str]:
    now = now or utcnow()
    messages = []
    horizon = (now + timedelta(days=7)).isoformat()
    for name, expires_at in vault.expiring(now, days=7):
        message = f"{name} expires at {expires_at} (within 7 days of {horizon})"
        queue.add("token_expiry", message)
        messages.append(message)
    return messages
