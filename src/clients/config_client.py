from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import CONFIG_SVC


class ConfigClient(BaseAhqClient):
    def __init__(self):
        super().__init__(CONFIG_SVC)

    async def list_environments(self) -> list:
        result = await self.get("/rest/api/environments")
        return result if isinstance(result, list) else result.get("content", result)

    async def get_environment(self, env_id: str) -> dict:
        return await self.get(f"/rest/api/environments/{env_id}")

    async def list_parameters(self) -> list:
        result = await self.get("/rest/api/parameters")
        return result if isinstance(result, list) else result.get("content", result)

    async def list_profiles(self) -> list:
        result = await self.get("/rest/api/profiles")
        return result if isinstance(result, list) else result.get("content", result)


config_client = ConfigClient()
