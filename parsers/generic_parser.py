from bs4 import BeautifulSoup

from parsers.base import BaseParser
from parsers.common import clean_soup, is_blocked_page
from utils.helpers import normalize_url


class GenericHtmlParser(BaseParser):
    name = "generic_html"

    def can_handle(self, url: str, html: str | None = None) -> bool:
        return True

    async def parse(self, url: str, session, html: str | None = None, title_from_page: str | None = None):
        if not html or is_blocked_page(html):
            return None

        soup = BeautifulSoup(html, "html.parser")
        soup = clean_soup(soup)

        title = title_from_page
        price = None
        availability = None

        if not title:
            title_selectors = [
                "h1.card-title.col-md-10",
                "h1.card-title",
                "h1.product-title",
                "h1.product-name",
                ".card-title.col-md-10",
                ".card-title",
                ".product-title",
                ".product-name",
                "h1",
            ]
            for selector in title_selectors:
                el = soup.select_one(selector)
                if el:
                    text = el.get_text(" ", strip=True)
                    if text:
                        title = text
                        break

        if not title and soup.title:
            title = soup.title.get_text(" ", strip=True)

        price_selectors = [
            "[data-product-price]",
            "[data-price]",
            ".price",
            ".product-price",
            ".price-item",
            ".sf-product__price",
            ".sf-prod__price",
            ".product__price",
        ]
        for selector in price_selectors:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(" ", strip=True)
                if text:
                    price = text
                    break

        availability_selectors = [
            "[data-product-status]",
            ".availability",
            "#availability",
            ".stock",
            ".preorder",
            ".delivery-info",
            ".product-form__buttons",
            ".product__availability",
        ]
        for selector in availability_selectors:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(" ", strip=True)
                if text:
                    availability = text
                    break

        body_text = " ".join(soup.get_text(" ", strip=True).split())[:1200]

        return {
            "source": "html_fallback",
            "url": normalize_url(url),
            "title": title,
            "price": price,
            "availability": availability,
            "body_text": body_text,
        }