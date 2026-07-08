from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AhqCredentials:
    """
    Per-tenant AHQ credentials. Threaded through every client instead of read from a global
    singleton, so the same process can serve multiple orgs/users (hosted HTTP mode) while stdio
    mode keeps using one fixed set of credentials from .env.
    """

    base_url: str
    api_token: str
    org_id: str
    project_id: str

    @classmethod
    def from_settings(cls, settings) -> "AhqCredentials":
        return cls(
            base_url=settings.ahq_base_url,
            api_token=settings.ahq_api_token,
            org_id=settings.ahq_org_id,
            project_id=settings.ahq_project_id,
        )

    @classmethod
    def from_headers(cls, headers: Mapping[str, str], base_url: str) -> "AhqCredentials":
        # base_url is never taken from the caller — always the server's own configured
        # AHQ_BASE_URL, so a header can't turn this into an open relay to an arbitrary host.
        return cls(
            base_url=base_url,
            api_token=headers.get("X-API-AUTH-KEY", ""),
            org_id=headers.get("org-id", ""),
            project_id=headers.get("projectId", ""),
        )
