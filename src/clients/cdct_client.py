from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import CDCT_SVC


def _unwrap(result) -> list:
    # cdct-core returns {"data": null} (not {"data": []}) when a list is empty — e.g.
    # MtafConsumerController.getAllConsumers() literally does
    # `return new MtafConsumerResponseList("No consumers found", 404, null)`.
    # Normalize to [] so callers never have to special-case None vs an empty list.
    if not isinstance(result, dict):
        return result
    return result.get("data") or []


class CdctClient(BaseAhqClient):
    """
    Consumer-Driven Contract Testing (Pact-based) — a niche capability for teams verifying that
    an API consumer and provider agree on a contract. Uses lowercase, hyphen-less
    organizationid/projectid headers (different convention from every other AHQ service).
    """

    def __init__(self, credentials=None, http_client=None):
        super().__init__(CDCT_SVC, credentials, http_client)
        self._org_project = {"organizationid": self._credentials.org_id, "projectid": self._credentials.project_id}

    # --- Consumers ---
    async def list_consumers(self) -> list:
        result = await self.get("/rest/api/consumers/list", extra_headers=self._org_project)
        return _unwrap(result)

    async def create_consumer(self, name: str) -> dict:
        return await self.post("/rest/api/consumers/create", json={"name": name}, extra_headers=self._org_project)

    async def get_consumer(self, consumer_id: str) -> dict:
        return await self.get(f"/rest/api/consumers/get/{consumer_id}", extra_headers=self._org_project)

    # --- Providers ---
    async def list_providers(self) -> list:
        result = await self.get("/rest/api/providers/list", extra_headers=self._org_project)
        return _unwrap(result)

    async def create_provider(self, name: str) -> dict:
        return await self.post("/rest/api/providers/create", json={"name": name}, extra_headers=self._org_project)

    async def get_provider(self, provider_id: str) -> dict:
        return await self.get(f"/rest/api/providers/get/{provider_id}", extra_headers=self._org_project)

    # --- Contracts ---
    async def list_contracts(self) -> list:
        result = await self.get("/rest/api/contracts/list", extra_headers=self._org_project)
        return _unwrap(result)

    async def create_contract(
        self,
        consumer_id: str,
        provider_id: str,
        method: str,
        contract_description: str = None,
        request_body: str = None,
        response_body: str = None,
    ) -> dict:
        payload = {"consumerId": consumer_id, "providerId": provider_id, "method": method}
        if contract_description:
            payload["contractDescription"] = contract_description
        if request_body:
            payload["requestBody"] = request_body
        if response_body:
            payload["responseBody"] = response_body
        return await self.post("/rest/api/contracts/create", json=payload, extra_headers=self._org_project)

    async def get_contract(self, contract_id: str) -> dict:
        return await self.get(f"/rest/api/contracts/get/{contract_id}", extra_headers=self._org_project)

    # --- Pact Runner ---
    async def run_provider_tests(self, contract_id: str) -> dict:
        return await self.post(f"/rest/api/pact-runner/run-provider-tests/{contract_id}")

    async def run_both_tests(self, contract_id: str) -> dict:
        return await self.post(f"/rest/api/pact-runner/run-both-consumer-provider-tests/{contract_id}")
