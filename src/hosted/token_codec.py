import base64
import hashlib
import json
import time

from cryptography.fernet import Fernet, InvalidToken


def derive_fernet_key(secret: str) -> bytes:
    """
    Fernet requires a urlsafe-base64 32-byte key; operators supply an arbitrary passphrase in
    AHQ_MCP_AUTH_SECRET, so hash it down to exactly that shape instead of making them generate
    a Fernet key by hand.
    """
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


class TokenCodec:
    """
    Encodes/decodes every piece of cross-request OAuth state as a self-contained
    Fernet-encrypted JSON blob, so the hosted server needs NO storage and any replica can
    complete a flow another replica started (pods are stateless; ArgoCD rolling deploys).
    Fernet gives authenticated encryption — blobs can't be read (they embed the user's AHQ
    API token) or forged without the shared secret.

    Kinds keep the blob types from being swapped for each other (an access token can't be
    replayed as an authorization code, etc.).
    """

    def __init__(self, secret: str):
        self._fernet = Fernet(derive_fernet_key(secret))

    def encode(self, kind: str, payload: dict, ttl_seconds: int) -> str:
        record = {"k": kind, "exp": int(time.time()) + int(ttl_seconds), **payload}
        return self._fernet.encrypt(json.dumps(record).encode()).decode()

    def decode(self, kind: str, blob: str) -> dict | None:
        """Returns the payload (still containing 'exp') or None on tamper/expiry/kind mismatch."""
        try:
            raw = self._fernet.decrypt(blob.encode())
        except (InvalidToken, TypeError, ValueError, AttributeError):
            return None
        try:
            record = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(record, dict) or record.pop("k", None) != kind:
            return None
        if record.get("exp", 0) < time.time():
            return None
        return record
