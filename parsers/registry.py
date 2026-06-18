from parsers.cardbuddys_parser import CardBuddysParser
from parsers.generic_parser import GenericHtmlParser
from parsers.shopify_parser import ShopifyParser
from utils.browser import fetch_page_with_playwright
from utils.logger import logger


class ParserRegistry:
    def __init__(self):
        self.shopify_parser = ShopifyParser()
        self.html_parsers = [
            CardBuddysParser(),
            GenericHtmlParser(),
        ]

    async def extract(self, url: str, session):
        if self.shopify_parser.can_handle(url):
            parsed = await self.shopify_parser.parse(url, session)
            if parsed:
                logger.info("Shopify-Daten erfolgreich extrahiert: %s", url)
                return parsed

        page_data = await fetch_page_with_playwright(url)
        if not page_data:
            logger.error("Keine Playwright-Daten fuer %s", url)
            return None

        html = page_data.get("html")
        title_from_page = page_data.get("title_from_page")

        for parser in self.html_parsers:
            if parser.can_handle(url, html):
                parsed = await parser.parse(url, session, html=html, title_from_page=title_from_page)
                if parsed:
                    logger.info("Parser %s erfolgreich fuer %s", parser.name, url)
                    return parsed

        logger.warning("Kein Parser konnte Daten extrahieren fuer %s", url)
        return None


parser_registry = ParserRegistry()