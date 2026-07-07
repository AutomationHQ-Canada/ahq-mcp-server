from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import (
    ASSET_SVC, TEST_MGMT_SVC, BACKGROUND_SVC, CONFIG_SVC,
    USER_MGMT_SVC, EXECUTOR_SVC, LOCAL_EXEC_SVC, STANDALONE_SVC,
    MANAGED_TEST_SVC, VIRT_CLIENT_SVC, VIRT_SERVER_SVC, CDCT_SVC, AUTH_SVC,
    settings,
)

# Maps user-friendly service name → gateway prefix
SERVICE_MAP = {
    "ahq-asset-services":                    ASSET_SVC,
    "ahq-test-management-services":          TEST_MGMT_SVC,
    "ahq-background-v2-services":            BACKGROUND_SVC,
    "ahq-config-services":                   CONFIG_SVC,
    "ahq-user-management-services":          USER_MGMT_SVC,
    "ahq-test-bot-executor-services":        EXECUTOR_SVC,
    "test-local-execution-services":         LOCAL_EXEC_SVC,
    "ahq-standalone-local-v2-services":      STANDALONE_SVC,
    "managed-testing-service-core":          MANAGED_TEST_SVC,
    "managed-testing-virtualization-client": VIRT_CLIENT_SVC,
    "managed-testing-virtualization-server": VIRT_SERVER_SVC,
    "mtaf-cdct-core":                        CDCT_SVC,
    "ahq-auth-services":                     AUTH_SVC,
    # short aliases
    "asset":          ASSET_SVC,
    "test-mgmt":      TEST_MGMT_SVC,
    "background":     BACKGROUND_SVC,
    "config":         CONFIG_SVC,
    "user-mgmt":      USER_MGMT_SVC,
    "executor":       EXECUTOR_SVC,
    "managed-testing": MANAGED_TEST_SVC,
    "cdct":           CDCT_SVC,
}

# Services that expose OpenAPI specs
OPENAPI_ENABLED = {
    ASSET_SVC, TEST_MGMT_SVC, CONFIG_SVC,
    USER_MGMT_SVC, EXECUTOR_SVC,
}


class GenericClient(BaseAhqClient):
    def __init__(self):
        super().__init__("")  # prefix is dynamic per call

    def _resolve(self, service_name: str) -> str:
        key = service_name.lower().strip()
        prefix = SERVICE_MAP.get(key)
        if not prefix:
            available = ", ".join(sorted(set(SERVICE_MAP.keys())))
            raise ValueError(f"Unknown service '{service_name}'. Available: {available}")
        return prefix

    async def get_service_spec(self, service_name: str) -> dict:
        prefix = self._resolve(service_name)
        if prefix not in OPENAPI_ENABLED:
            return {
                "error": f"{service_name} does not expose an OpenAPI spec.",
                "note": "ahq-background-v2-services has no springdoc dependency.",
            }
        return await self._request(
            "GET", f"{settings.ahq_base_url}{prefix}/v3/api-docs", timeout=15
        )

    async def call_api(
        self,
        service: str,
        method: str,
        path: str,
        body: dict = None,
        params: dict = None,
        extra_headers: dict = None,
    ) -> dict:
        prefix = self._resolve(service)
        url = f"{settings.ahq_base_url}{prefix}{path}"

        return await self._request(
            method.upper(), url, json=body, params=params, extra_headers=extra_headers, timeout=30
        )


generic_client = GenericClient()
