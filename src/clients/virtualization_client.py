from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import VIRT_SERVER_SVC


class VirtualizationClient(BaseAhqClient):
    """
    Service virtualization (WireMock-backed API mocking). Deliberately wraps only
    managed-testing-virtualization-server, not the near-duplicate -client variant — the two
    controllers are almost identical and exposing both would just give two tools for one job.
    """

    def __init__(self):
        super().__init__(VIRT_SERVER_SVC)

    async def list_mock_mappings(self, method: str = None, search: str = None) -> dict:
        params = {}
        if method:
            params["method"] = method
        if search:
            params["search"] = search
        return await self.get("/api/virtualization/get-mappings", params=params or None)

    async def get_mock_mapping(self, mapping_id: str):
        return await self.get(f"/api/virtualization/get-mappings/{mapping_id}")

    async def get_mock_mapping_template(self):
        return await self.get("/api/virtualization/mapping-template")

    async def create_mock_mapping(self, mapping: dict):
        import json as _json
        # The controller's @RequestBody is a raw String, not a typed object — send as
        # text/plain (like import_curl) so Spring's StringHttpMessageConverter reads it
        # as-is instead of Jackson trying (and failing) to deserialize an object into a String.
        return await self._request(
            "POST",
            f"{self._base}/api/virtualization/add-mapping",
            content=_json.dumps(mapping),
            extra_headers={"Content-Type": "text/plain"},
            timeout=30,
        )

    async def delete_mock_mapping(self, mapping_id: str):
        return await self.delete(f"/api/virtualization/delete-mapping/{mapping_id}")


virtualization_client = VirtualizationClient()
