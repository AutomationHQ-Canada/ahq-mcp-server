import base64
import json
from dataclasses import dataclass
from typing import Mapping


def decode_ahq_token(token: str) -> dict:
    """
    Decodes an AHQ ORGANIZATION JWT's claims WITHOUT verifying the signature — this is safe here
    because we're not authenticating the caller, just reading back identity fields the gateway
    itself already trusts (the gateway does the real signature/lookup validation against Mongo's
    `tokens` collection). Used to derive organizationId directly from the token instead of trusting
    a separately-configured value that can drift out of sync with it.
    """
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


@dataclass(frozen=True)
class AhqCredentials:
    """
    Per-tenant AHQ credentials. Threaded through every client instead of read from a global
    singleton, so the same process can serve multiple orgs/users (hosted HTTP mode) while stdio
    mode keeps using one fixed set of credentials from .env.

    org_id is ALWAYS derived from the token's own `organizationId` claim, never from a
    separately-configured value — a stale/mismatched org_id silently writes real data into the
    wrong organization (confirmed live, 2026-07-08: a wrong AHQ_ORG_ID in .env matched neither the
    token's own org nor anything the user could see, and every API call still "succeeded" since the
    gateway doesn't validate the header against the token's claim). project_id has no equivalent
    claim in the token (an ORGANIZATION token isn't scoped to one project) and must still be
    configured explicitly.
    """

    base_url: str
    api_token: str
    org_id: str
    project_id: str

    @classmethod
    def from_settings(cls, settings) -> "AhqCredentials":
        claims = decode_ahq_token(settings.ahq_api_token)
        return cls(
            base_url=settings.ahq_base_url,
            api_token=settings.ahq_api_token,
            org_id=claims["organizationId"],
            project_id=settings.ahq_project_id,
        )

    @classmethod
    def from_headers(cls, headers: Mapping[str, str], base_url: str) -> "AhqCredentials":
        # base_url is never taken from the caller — always the server's own configured
        # AHQ_BASE_URL, so a header can't turn this into an open relay to an arbitrary host.
        token = headers.get("X-API-AUTH-KEY", "")
        org_id = ""
        if token:
            try:
                org_id = decode_ahq_token(token).get("organizationId", "")
            except Exception:
                org_id = ""
        return cls(
            base_url=base_url,
            api_token=token,
            org_id=org_id,
            project_id=headers.get("projectId", ""),
        )
