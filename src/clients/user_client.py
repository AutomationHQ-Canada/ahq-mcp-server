from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import USER_MGMT_SVC


class UserClient(BaseAhqClient):
    def __init__(self):
        super().__init__(USER_MGMT_SVC)

    async def get_current_user(self) -> dict:
        return await self.get("/rest/api/users/me")

    async def list_projects(self) -> list:
        result = await self.get("/rest/api/projects")
        return result if isinstance(result, list) else result.get("content", result)

    async def list_users(self) -> list:
        result = await self.get("/rest/api/users")
        return result if isinstance(result, list) else result.get("content", result)


user_client = UserClient()
