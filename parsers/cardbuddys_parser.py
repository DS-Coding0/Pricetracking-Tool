from urllib.parse import urlparse

from bs4 import BeautifulSoup

from parsers.base import BaseParser
from parsers.common import clean_soup, is_blocked_page
from utils.helpers import normalize_url


class CardBuddysParser(BaseParser):
    name = "cardbuddys"

    def can_handle(self, url: str, html: str | None = None) -> bool:
        return "cardbuddys.de" in urlparse(url).netloc

    async def parse(self, url: str, session, html: str | None = None, title_from_page: str | None = None):
        if not html or is_blocked_page(html):
            return None

        soup = BeautifulSoup(html, "html.parser")
        soup = clean_soup(soup)

        title = title_from_page
        if not title:
            el = soup.select_one("h1.card-title.col-md-10") or soup.select_one("h1.card-title") or soup.select_one("h1")
            if el:
                title = el.get_text(" ", strip=True)

        price = None
        for selector in [".price", ".product-price", ".price-item", "[data-price]"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(" ", strip=True)
                if text:
                    price = text
                    break

        availability = None
        for selector in [".delivery-info", ".availability", "#availability", ".product-form__buttons"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(" ", strip=True)
                if text:
                    availability = text
                    break

        body_text = " ".join(soup.get_text(" ", strip=True).split())[:1200]

        return {
            "source": "cardbuddys_html",
            "url": normalize_url(url),
            "title": title,
            "price": price,
            "availability": availability,
            "body_text": body_text,
        }