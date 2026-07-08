from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import ASSET_SVC


class AssetClient(BaseAhqClient):
    def __init__(self, credentials=None, http_client=None):
        super().__init__(ASSET_SVC, credentials, http_client)

    async def validate_token(self) -> dict:
        import base64, json
        payload = self._credentials.api_token.split(".")[1]
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
        # Returns an ObjectRepository: {"name": "Object Repository", "pages": [...]} — NOT
        # {"content": [...]} like the other list_* endpoints in this service.
        result = await self.get(
            f"/rest/api/websites/{website_id}/pages/list",
            params={"size": 1000},
        )
        return result if isinstance(result, list) else result.get("pages", result)

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
    async def add_locators(self, page_id: str, website_id: str, page_url: str, page_name: str, locators: list) -> dict:
        # pushSpyElements expects a raw JSON array of full Page objects (each with its locators
        # embedded), NOT {"pageId": ..., "elements": [...]} - confirmed against the real
        # LocatorController.pushSpyElements(@RequestBody List<Page> pages). It upserts by
        # pageUrl match (findBy...PageUrl...), so page_url must be included or this creates a
        # duplicate page instead of merging into the one just created via create_page.
        page_payload = {
            "pageId": page_id,
            "pageName": page_name,
            "pageUrl": page_url,
            "websiteId": website_id,
            "locators": locators,
        }
        return await self.post(
            "/rest/api/locators/pushSpyElements",
            json=[page_payload],
            extra_headers={"websiteId": website_id},
            timeout=60,
        )
