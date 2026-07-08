from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import ASSET_SVC
from src.config.credentials import decode_ahq_token


class AssetClient(BaseAhqClient):
    def __init__(self, credentials=None, http_client=None):
        super().__init__(ASSET_SVC, credentials, http_client)

    async def validate_token(self) -> dict:
        claims = decode_ahq_token(self._credentials.api_token)
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
        #
        # ActionLibraryServices.getLocatorBy()/getLocatorValue() (ahq-actions-commons) has a real
        # bug: two separate `if` statements instead of `if/else if`, so it calls .isEmpty() on
        # locator.getLocateBy() even after already detecting it's null, throwing an NPE at
        # execution time - confirmed live, execution failed on step 2 with exactly this NPE.
        # This only bites locators created via locationStrategies alone (the modern, correct way,
        # which is all pushSpyElements needs) - the UI's own recorder/manual-entry flow apparently
        # always double-writes the deprecated singular locateBy/locatorValue fields too, so it
        # never trips this. Mirror that behavior here as a defensive workaround until the real bug
        # is fixed upstream: populate locateBy/locatorValue from the selected (or first) strategy.
        for loc in locators:
            strategies = loc.get("locationStrategies") or []
            if strategies and not loc.get("locateBy"):
                chosen = next((s for s in strategies if s.get("selected")), strategies[0])
                loc["locateBy"] = chosen.get("locateBy", "")
                loc["locatorValue"] = chosen.get("locatorValue", "")

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

    async def update_locator(
        self, website_id: str, page_id: str, locator_id: str, locator_name: str, locator_type: str, locate_by: str, locator_value: str
    ) -> dict:
        # add_locators (pushSpyElements) only ADDS locators that don't already match an existing
        # one by locationStrategies value (LocatorController.mergeLocators/strategiesMatch) — it
        # silently no-ops for anything that already exists, never updating fields on it. This is
        # the only way to actually fix an already-created locator (e.g. backfilling
        # locateBy/locatorValue on one created before that fix existed).
        body = {
            "locatorId": locator_id,
            "locatorName": locator_name,
            "locatorType": locator_type,
            "locateBy": locate_by,
            "locatorValue": locator_value,
            "locationStrategies": [{"locateBy": locate_by, "locatorValue": locator_value, "selected": True}],
        }
        return await self.put(f"/rest/api/websites/{website_id}/pages/{page_id}/locator/{locator_id}", json=body)
