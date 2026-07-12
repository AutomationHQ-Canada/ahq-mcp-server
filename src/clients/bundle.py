from dataclasses import dataclass

import httpx

from src.config.credentials import AhqCredentials
from src.clients.asset_client import AssetClient
from src.clients.test_mgmt_client import TestMgmtClient
from src.clients.background_client import BackgroundClient
from src.clients.config_client import ConfigClient
from src.clients.user_client import UserClient
from src.clients.executor_client import ExecutorClient
from src.clients.generic_client import GenericClient
from src.clients.local_exec_client import LocalExecClient
from src.clients.managed_testing_client import ManagedTestingClient
from src.clients.email_client import EmailClient
from src.clients.cdct_client import CdctClient
from src.clients.virtualization_client import VirtualizationClient
from src.clients.tunnel_client import TunnelClient


@dataclass
class ClientBundle:
    """
    One set of AHQ clients, all sharing the same credentials (and, in HTTP mode, the same
    pooled httpx.AsyncClient). stdio mode uses DEFAULT_BUNDLE (credentials from .env, one per
    process); hosted HTTP mode builds one bundle per request from that request's headers.
    """

    asset: AssetClient
    test_mgmt: TestMgmtClient
    background: BackgroundClient
    config: ConfigClient
    user: UserClient
    executor: ExecutorClient
    generic: GenericClient
    local_exec: LocalExecClient
    managed_testing: ManagedTestingClient
    email: EmailClient
    cdct: CdctClient
    virtualization: VirtualizationClient
    tunnel: TunnelClient

    @classmethod
    def build(cls, credentials: AhqCredentials = None, http_client: httpx.AsyncClient = None) -> "ClientBundle":
        kw = dict(credentials=credentials, http_client=http_client)
        return cls(
            asset=AssetClient(**kw),
            test_mgmt=TestMgmtClient(**kw),
            background=BackgroundClient(**kw),
            config=ConfigClient(**kw),
            user=UserClient(**kw),
            executor=ExecutorClient(**kw),
            generic=GenericClient(**kw),
            local_exec=LocalExecClient(**kw),
            managed_testing=ManagedTestingClient(**kw),
            email=EmailClient(**kw),
            cdct=CdctClient(**kw),
            virtualization=VirtualizationClient(**kw),
            tunnel=TunnelClient(**kw),
        )


DEFAULT_BUNDLE = ClientBundle.build()
