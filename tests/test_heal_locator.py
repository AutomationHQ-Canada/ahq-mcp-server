from src.tools.heal_locator import _match_score, _similarity, MIN_MATCH_SCORE


def test_similarity_is_case_insensitive_and_symmetric():
    assert _similarity("Submit Button", "submit button") == 1.0
    assert _similarity("Submit Button", "Button Submit") == _similarity("Button Submit", "Submit Button")


def test_similarity_is_zero_for_empty_input():
    assert _similarity("", "Submit Button") == 0.0
    assert _similarity("Submit Button", "") == 0.0


def test_match_score_takes_best_field_not_average():
    element = {"text": "totally unrelated", "ariaLabel": "Submit Button", "placeholder": "", "name": ""}
    score = _match_score("Submit Button", element)
    assert score == 1.0


def test_match_score_below_threshold_for_unrelated_element():
    element = {"text": "Cancel", "ariaLabel": "", "placeholder": "", "name": ""}
    score = _match_score("Environment Option - dev", element)
    assert score <= MIN_MATCH_SCORE


async def test_heal_locator_reports_error_when_locator_missing_from_page():
    from src.tools.heal_locator import heal_locator

    class FakeAssetClient:
        async def get_page_by_locator_id(self, website_id, locator_id):
            return {"pageId": "page-1", "pageUrl": "https://example.com", "locators": []}

    result = await heal_locator(FakeAssetClient(), "loc-missing", "site-1")
    assert "error" in result
    assert "loc-missing" in result["error"]


async def test_heal_locator_reports_error_when_page_has_no_url():
    from src.tools.heal_locator import heal_locator

    class FakeAssetClient:
        async def get_page_by_locator_id(self, website_id, locator_id):
            return {"pageId": "page-1", "pageUrl": "", "locators": [{"locatorId": locator_id, "locatorName": "Submit"}]}

    result = await heal_locator(FakeAssetClient(), "loc-1", "site-1")
    assert "error" in result


async def test_heal_locator_blocks_non_public_url_when_hosted():
    from src.tools.heal_locator import heal_locator

    class FakeAssetClient:
        async def get_page_by_locator_id(self, website_id, locator_id):
            return {
                "pageId": "page-1",
                "pageUrl": "http://localhost:9202/internal",
                "locators": [{"locatorId": locator_id, "locatorName": "Submit"}],
            }

    result = await heal_locator(FakeAssetClient(), "loc-1", "site-1", hosted=True)
    assert "error" in result
