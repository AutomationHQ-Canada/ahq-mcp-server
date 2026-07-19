import asyncio

from urllib.parse import urlparse
from playwright.async_api import async_playwright, Page

from src.config.ahq_services import settings
from src.tools.url_guard import validate_public_http_url

MAX_PAGES = 20
NETWORK_IDLE_TIMEOUT = 10_000  # ms

# Hosted pods serve many tenants: cap simultaneous headless-Chromium instances so N users
# crawling at once can't OOM the pod (memory is sized for ~this many browsers, see the Helm
# values). Waiting callers just queue on the semaphore; the MCP client's own request timeout
# is the backstop.
_CRAWL_SEMAPHORE = asyncio.Semaphore(max(1, settings.ahq_mcp_crawl_concurrency))


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


async def crawl_url(url: str, credentials: dict = None, max_pages: int = MAX_PAGES,
                    hosted: bool = False) -> dict:
    if hosted:
        # SSRF guard (Slice 9j): a hosted crawl runs INSIDE the cluster, so a crafted URL
        # (or a same-domain link found while crawling) must never reach private/metadata
        # addresses. Checked here for the entry URL and again on every dequeued URL below —
        # per-navigation DNS re-resolution is the guard; the rebinding TOCTOU window between
        # check and goto is a documented accepted residual risk (Playwright can't pin IPs).
        blocked = await validate_public_http_url(url)
        if blocked:
            return {"error": blocked}

    async with _CRAWL_SEMAPHORE:
        return await _crawl(url, credentials, max_pages, hosted)


async def _crawl(url: str, credentials: dict, max_pages: int, hosted: bool) -> dict:
    base_domain = urlparse(url).netloc
    visited: set[str] = set()
    pages_data = []

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:
            # The classic playwright pip-vs-browser mismatch: the installed playwright package
            # expects a specific chromium build (e.g. chromium-1228) that `playwright install`
            # hasn't downloaded yet — happens after any playwright version bump. Return an
            # actionable error instead of a raw "Executable doesn't exist" traceback.
            if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
                return {
                    "error": (
                        "Playwright's browser binary is missing or out of date for the installed "
                        "playwright package. Fix: run `playwright install chromium` in this "
                        "environment (required once after every playwright version bump), then retry."
                    )
                }
            raise
        context = await browser.new_context()

        if credentials:
            login_page = await context.new_page()
            await login_page.goto(url, wait_until="networkidle", timeout=30_000)
            try:
                # Scope username/submit lookups to the <form> containing the password field,
                # not the whole page. A login page commonly also has a nearby "Sign Up" button
                # (confirmed live against app.automationhq.ai: both "SIGN IN" and "Sign Up" are
                # button[type="submit"]) — an unscoped selector matches both, Playwright's
                # strict-mode click throws on the ambiguity, and the bare except below swallowed
                # it silently, so the form was never actually submitted despite no visible error.
                password_field = login_page.locator('input[type="password"]').first
                form = password_field.locator("xpath=ancestor::form[1]")
                await form.locator(
                    'input[type="email"], input[name*="user"], input[name*="email"]'
                ).first.fill(credentials.get("username", ""))
                await password_field.fill(credentials.get("password", ""))
                start_url = login_page.url
                await form.locator('button[type="submit"], input[type="submit"]').first.click()
                # networkidle alone races the SPA's post-login redirect: there's commonly a brief
                # network lull right after the login API call resolves and before the client-side
                # navigation to the authenticated area actually starts, so wait_for_load_state can
                # return while still sitting on the login URL (confirmed live against
                # app.automationhq.ai: login → /checking → /{org}/{project}/dashboard). Wait for the
                # URL to actually change first, then let it settle. A prior version of this fix
                # checked `"login" not in u.lower()` instead of comparing against `start_url` — that
                # is trivially true from the very first instant whenever the caller's own crawl
                # target (the page we log in FROM) doesn't itself contain the substring "login" (e.g.
                # this app's bare root "/" also renders the login form), making the wait a same-tick
                # no-op and leaving the exact race it was meant to close (confirmed live: crawl_url
                # against "https://app.automationhq.ai/" still only ever discovered the 4 pre-auth
                # pages). Comparing against the URL actually seen before the click, whatever it was,
                # correctly catches the first real navigation (to the transitional "/checking" page)
                # regardless of what the starting URL happens to be.
                try:
                    await login_page.wait_for_url(lambda u: u != start_url, timeout=15_000)
                except Exception:
                    pass
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

            if hosted:
                blocked = await validate_public_http_url(current_url)
                if blocked:
                    pages_data.append({"url": current_url, "error": blocked})
                    continue

            try:
                page = await context.new_page()
                # domcontentloaded is the hard requirement — networkidle is best-effort only.
                # A page that keeps a persistent connection open (websocket/long-polling) never
                # goes network-idle, which would otherwise block the crawl on that page forever.
                await page.goto(current_url, wait_until="domcontentloaded", timeout=NETWORK_IDLE_TIMEOUT + 20_000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)
                except Exception:
                    pass
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
                        parsed.scheme in ("http", "https")
                        and parsed.netloc == base_domain
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
