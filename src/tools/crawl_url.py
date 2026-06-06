from urllib.parse import urlparse
from playwright.async_api import async_playwright, Page

MAX_PAGES = 20
NETWORK_IDLE_TIMEOUT = 10_000  # ms


async def _extract_locators(page: Page) -> list[dict]:
    return await page.evaluate("""() => {
        const elements = [];
        const interactable = document.querySelectorAll(
            'a, button, input, select, textarea, [role="button"], [role="link"], [role="menuitem"], [onclick]'
        );

        const getXPath = (el) => {
            if (el.id) return `//*[@id="${el.id}"]`;
            if (el === document.body) return '/html/body';
            const siblings = el.parentNode.childNodes;
            let pos = 0;
            for (let i = 0; i < siblings.length; i++) {
                if (siblings[i] === el) break;
                if (siblings[i].nodeType === 1 && siblings[i].tagName === el.tagName) pos++;
            }
            return `${getXPath(el.parentNode)}/${el.tagName.toLowerCase()}[${pos + 1}]`;
        };

        interactable.forEach((el) => {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return;

            let css = null;
            if (el.id) {
                css = `#${el.id}`;
            } else if (el.getAttribute('data-testid')) {
                css = `[data-testid="${el.getAttribute('data-testid')}"]`;
            } else if (el.getAttribute('aria-label')) {
                css = `[aria-label="${el.getAttribute('aria-label')}"]`;
            } else {
                css = el.tagName.toLowerCase() +
                    (el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
            }

            elements.push({
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || null,
                text: (el.innerText || el.value || '').trim().slice(0, 100),
                ariaLabel: el.getAttribute('aria-label') || null,
                placeholder: el.getAttribute('placeholder') || null,
                id: el.id || null,
                name: el.getAttribute('name') || null,
                css: css,
                xpath: getXPath(el),
            });
        });
        return elements;
    }""")


async def _validate_locators(page: Page, locators: list[dict]) -> list[dict]:
    valid = []
    for loc in locators:
        resolved = False
        try:
            if loc.get("css"):
                if await page.locator(loc["css"]).count() > 0:
                    resolved = True
        except Exception:
            pass

        if not resolved:
            try:
                if loc.get("xpath"):
                    if await page.locator(f"xpath={loc['xpath']}").count() > 0:
                        resolved = True
            except Exception:
                pass

        if resolved:
            valid.append(loc)
    return valid


async def crawl_url(url: str, credentials: dict = None, max_pages: int = MAX_PAGES) -> dict:
    base_domain = urlparse(url).netloc
    visited: set[str] = set()
    pages_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        if credentials:
            login_page = await context.new_page()
            await login_page.goto(url, wait_until="networkidle", timeout=30_000)
            try:
                await login_page.fill(
                    'input[type="email"], input[name*="user"], input[name*="email"]',
                    credentials.get("username", ""),
                )
                await login_page.fill('input[type="password"]', credentials.get("password", ""))
                await login_page.click('button[type="submit"], input[type="submit"]')
                await login_page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            await login_page.close()

        queue = [url]

        while queue and len(visited) < max_pages:
            current_url = queue.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                page = await context.new_page()
                await page.goto(current_url, wait_until="networkidle", timeout=NETWORK_IDLE_TIMEOUT + 20_000)
                await page.wait_for_timeout(1_000)

                title = await page.title()
                locators = await _extract_locators(page)
                valid_locators = await _validate_locators(page, locators)

                total = len(locators)
                valid = len(valid_locators)
                resolution_rate = round(valid / total, 2) if total > 0 else 0.0

                pages_data.append({
                    "url": current_url,
                    "title": title,
                    "locators": valid_locators,
                    "total_found": total,
                    "total_valid": valid,
                    "resolution_rate": resolution_rate,
                    "passes_threshold": resolution_rate >= 0.80,
                })

                links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                for link in links:
                    parsed = urlparse(link)
                    if (
                        parsed.netloc == base_domain
                        and link not in visited
                        and link not in queue
                    ):
                        queue.append(link)

                await page.close()

            except Exception as e:
                pages_data.append({"url": current_url, "error": str(e)})

        await browser.close()

    total_locators = sum(p.get("total_valid", 0) for p in pages_data)
    return {
        "pages_crawled": len([p for p in pages_data if "error" not in p]),
        "total_locators": total_locators,
        "pages": pages_data,
    }
