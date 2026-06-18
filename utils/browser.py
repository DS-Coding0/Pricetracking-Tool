from playwright.async_api import async_playwright

from utils.config import HEADERS
from utils.logger import logger


async def fetch_page_with_playwright(url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                locale="de-DE",
                user_agent=HEADERS["User-Agent"]
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            title_from_page = None
            title_selectors = [
                "h1.card-title.col-md-10",
                "h1.card-title",
                "h1.product-title",
                "h1",
            ]

            for selector in title_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    locator = page.locator(selector).first
                    text = await locator.text_content()
                    if text and text.strip():
                        title_from_page = text.strip()
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(2000)
            html = await page.content()
            await browser.close()

            return {
                "html": html,
                "title_from_page": title_from_page
            }

    except Exception as e:
        logger.error("Playwright-Fehler fuer %s: %s", url, e)
        return None