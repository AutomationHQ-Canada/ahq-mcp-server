from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import ASSET_SVC


class AssetClient(BaseAhqClient):
    def __init__(self):
        super().__init__(ASSET_SVC)

    async def validate_token(self) -> dict:
        from src.config.ahq_services import settings
        import base64, json
        payload = settings.ahq_api_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        org_name = claims.get("organizationName", "unknown org")
        created_by = claims.get("createdByUserId", "unknown")
        return {"name": org_name, "userId": created_by, "tokenType": claims.get("tokenType", "UNKNOWN")}

    # --- Websites ---
    async def list_websites(self) -> list:
        result = await self.get("/rest/api/websites/list", params={"size": 1000})
        return result if isinstance(result, list) else result.get("content", result)

    async def search_websites(self, name: str) -> list:
        return await self.get("/rest/api/websites/list/search", params={"search": name})

    async def create_website(self, name: str, url: str) -> dict:
        return await self.post("/rest/api/websites", json={"name": name, "url": url})

    async def get_website(self, website_id: str) -> dict:
        return await self.get(f"/rest/api/websites/{website_id}")

    # --- Pages ---
    async def list_pages(self, website_id: str) -> list:
        result = await self.get(
            f"/rest/api/websites/{website_id}/pages/list",
            params={"size": 1000},
        )
        return result if isinstance(result, list) else result.get("content", result)

    async def create_page(self, website_id: str, name: str, url: str = "") -> dict:
        return await self.post(
            f"/rest/api/websites/{website_id}/pages",
            json={"pageName": name, "pageUrl": url},
        )

    async def get_page_by_url(self, website_id: str, url: str) -> dict:
        return await self.get(
            "/rest/api/locators/byPage",
            params={"url": url},
            extra_headers={"websiteId": website_id},
        )

    # --- Locators ---
    async def add_locators(self, page_id: str, website_id: str, locators: list) -> dict:
        return await self.post(
            "/rest/api/locators/pushSpyElements",
            json={"pageId": page_id, "elements": locators},
            extra_headers={"websiteId": website_id},
            timeout=60,
        )


asset_client = AssetClient()
