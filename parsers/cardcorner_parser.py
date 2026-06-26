import logging
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from parsers.base import BaseParser
from parsers.common import clean_soup, is_blocked_page
from utils.helpers import normalize_url


logger = logging.getLogger("price_tracker")


class CardCornerParser(BaseParser):
    name = "cardcorner"

    SCHEMA_AVAILABILITY_MAP = {
        "https://schema.org/InStock": "in_stock",
        "https://schema.org/OutOfStock": "out_of_stock",
        "https://schema.org/PreOrder": "preorder",
        "https://schema.org/PreSale": "presale",
        "https://schema.org/LimitedAvailability": "limited",
        "https://schema.org/Discontinued": "discontinued",
        "https://schema.org/SoldOut": "out_of_stock",
    }

    def can_handle(self, url: str, html: str | None = None) -> bool:
        return "card-corner.de" in urlparse(url).netloc.lower()

    async def parse(
        self,
        url: str,
        session,
        html: str | None = None,
        title_from_page: str | None = None,
    ):
        if not html:
            logger.debug("CardCorner: no html for %s", url)
            return None

        if is_blocked_page(html):
            logger.debug("CardCorner: blocked page detected for %s", url)
            return None

        soup = clean_soup(BeautifulSoup(html, "html.parser"))

        product_root = self._get_product_root(soup)
        if not product_root:
            logger.debug("CardCorner: no product root found for %s", url)
            return None

        product_details = (
            product_root.select_one(".product-details")
            or product_root.select_one(".product-details-inner")
            or product_root
        )

        offer_root = (
            product_details.select_one(".product-offer")
            or product_root.select_one(".product-details .product-offer")
            or product_root.select_one(".product-offer")
            or product_root.select_one("#product-offer")
        )

        logger.debug(
            "CardCorner roots for %s: product_root=%s product_details=%s offer_root=%s",
            url,
            bool(product_root),
            bool(product_details),
            bool(offer_root),
        )

        title = (
            self._clean_text(title_from_page)
            or self._first_text(
                product_root,
                [
                    ".product-headline h2.product-title[itemprop='name']",
                    ".product-headline .product-title[itemprop='name']",
                    ".product-headline h2.product-title",
                    ".product-headline .product-title",
                    "h2.product-title.h2[itemprop='name']",
                    "h2.product-title.h2",
                    "[itemprop='name']",
                ],
            )
        )

        sku = self._first_text(
            product_root,
            [
                ".product-sku [itemprop='sku']",
                "[itemprop='sku']",
            ],
        )

        brand = self._first_text(
            product_root,
            [
                ".product-manufacturer [itemprop='name']",
                "[itemprop='brand'] [itemprop='name']",
                ".product-manufacturer",
            ],
        )

        category = self._first_text(
            product_root,
            [
                ".product-category [itemprop='category']",
                "[itemprop='category']",
            ],
        )

        image_url = self._first_attr(
            product_root,
            [
                ("meta[itemprop='image']", "content"),
                ("img.product-image", "src"),
            ],
        )

        short_description = self._first_text(
            product_root,
            [
                ".shortdesc[itemprop='description']",
                ".shortdesc",
                "[itemprop='description']",
            ],
        )

        price_label = self._first_text(
            offer_root,
            [
                ".pricewrapper .pricelabel.priceonapplication",
                ".pricewrapper .pricelabel",
                ".pricelabel.priceonapplication",
                ".pricelabel",
            ],
        )

        price_amount_raw = self._first_attr(
            offer_root,
            [
                ("meta[itemprop='price']", "content"),
            ],
        )

        visible_price = self._first_text(
            offer_root,
            [
                ".pricewrapper .price",
                ".pricewrapper .price.h1",
                ".price.h1",
                "[itemprop='price']",
            ],
        )

        price_currency = self._first_attr(
            offer_root,
            [
                ("meta[itemprop='priceCurrency']", "content"),
            ],
        )

        availability_schema = self._first_attr(
            product_details,
            [
                ("link[itemprop='availability']", "href"),
            ],
        )

        availability_text = self._first_text(
            product_details,
            [
                ".delivery-status .status",
                ".delivery-status",
                ".availability",
                "#availability",
            ],
        )

        logger.debug(
            "CardCorner extracted fields for %s: title=%r price_label=%r price_amount_raw=%r "
            "visible_price=%r price_currency=%r availability_schema=%r availability_text=%r "
            "sku=%r brand=%r category=%r image_url=%r",
            url,
            title,
            price_label,
            price_amount_raw,
            visible_price,
            price_currency,
            availability_schema,
            availability_text,
            sku,
            brand,
            category,
            image_url,
        )

        availability_status = self._normalize_availability(
            availability_schema=availability_schema,
            availability_text=availability_text,
            price_label=price_label,
        )

        has_non_sale_label = self._is_non_sale_label(price_label)

        price_amount = None
        if not has_non_sale_label:
            price_amount = self._normalize_price_amount(price_amount_raw or visible_price)

        if has_non_sale_label:
            logger.debug(
                "CardCorner: suppress numeric price because label is non-sale for %s: %r",
                url,
                price_label,
            )

        if availability_status in {"out_of_stock", "coming_soon"} and price_amount is not None:
            logger.debug(
                "CardCorner: suppress numeric price because availability=%s for %s",
                availability_status,
                url,
            )
            price_amount = None

        price_text = None
        if price_amount is not None and price_currency:
            price_text = f"{price_amount} {price_currency}"
        elif price_amount is not None:
            price_text = price_amount
        elif price_label:
            price_text = self._clean_text(price_label)

        sale_state = self._derive_sale_state(
            price_amount=price_amount,
            price_label=price_label,
            availability_status=availability_status,
        )

        body_text = self._extract_body_text(product_root)

        result = {
            "source": "cardcorner_html",
            "parser": self.name,
            "url": normalize_url(url),
            "title": title,
            "price": price_text,
            "price_amount": price_amount,
            "price_currency": price_currency if price_amount is not None else None,
            "price_label": self._clean_text(price_label),
            "availability": availability_status,
            "availability_text": self._clean_text(availability_text),
            "availability_schema": availability_schema,
            "sale_state": sale_state,
            "short_description": self._clean_text(short_description),
            "sku": self._clean_text(sku),
            "brand": self._clean_text(brand),
            "category": self._clean_text(category),
            "image_url": image_url,
            "body_text": body_text,
        }

        logger.debug("CardCorner final result for %s: %s", url, result)

        if not any([result["title"], result["price"], result["availability"], result["short_description"]]):
            return None

        return result

    def _get_product_root(self, soup: BeautifulSoup):
        selectors = [
            "#result-wrapper[itemprop='mainEntity'][itemtype='https://schema.org/Product']",
            "#result-wrapper[itemprop='mainEntity']",
            "[itemprop='mainEntity'][itemtype='https://schema.org/Product']",
            "#result-wrapper",
        ]
        for selector in selectors:
            el = soup.select_one(selector)
            if el:
                logger.debug("CardCorner product root matched: %s", selector)
                return el
        return None

    def _first_text(self, root, selectors: list[str]) -> str | None:
        if root is None:
            return None

        for selector in selectors:
            el = root.select_one(selector)
            if not el:
                continue

            value = el.get_text(" ", strip=True)
            value = self._clean_text(value)
            if value:
                logger.debug("CardCorner _first_text matched %s => %r", selector, value)
                return value
        return None

    def _first_attr(self, root, candidates: list[tuple[str, str]]) -> str | None:
        if root is None:
            return None

        for selector, attr in candidates:
            el = root.select_one(selector)
            if not el:
                continue

            value = self._clean_text(el.get(attr))
            if value:
                logger.debug(
                    "CardCorner _first_attr matched %s[%s] => %r",
                    selector,
                    attr,
                    value,
                )
                return value
        return None

    def _clean_text(self, value: str | None) -> str | None:
        if not value:
            return None
        value = value.replace("\xa0", " ")
        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    def _normalize_price_amount(self, raw_value: str | None) -> str | None:
        if not raw_value:
            return None

        cleaned = self._clean_text(raw_value)
        if not cleaned:
            return None

        match = re.search(r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})|\d+(?:[.,]\d{2})?)", cleaned)
        if not match:
            logger.debug("CardCorner no numeric price found in %r", cleaned)
            return None

        number = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
        try:
            normalized = format(Decimal(number), "f")
            logger.debug("CardCorner normalized price %r => %s", cleaned, normalized)
            return normalized
        except (InvalidOperation, ValueError):
            logger.debug("CardCorner failed to normalize price %r", cleaned)
            return None

    def _is_non_sale_label(self, price_label: str | None) -> bool:
        if not price_label:
            return False

        lowered = price_label.lower()
        return any(token in lowered for token in [
            "verkauf startet bald",
            "coming soon",
            "bald verfügbar",
            "bald verfugbar",
            "demnächst verfügbar",
            "demnachst verfugbar",
        ])

    def _normalize_availability(
        self,
        availability_schema: str | None,
        availability_text: str | None,
        price_label: str | None,
    ) -> str | None:
        if availability_schema and availability_schema in self.SCHEMA_AVAILABILITY_MAP:
            mapped = self.SCHEMA_AVAILABILITY_MAP[availability_schema]
            logger.debug("CardCorner availability from schema %r => %s", availability_schema, mapped)
            return mapped

        for candidate in [availability_text, price_label]:
            candidate = self._clean_text(candidate)
            if not candidate:
                continue
            lowered = candidate.lower()

            if "ausverkauft" in lowered:
                return "out_of_stock"
            if "verkauf startet bald" in lowered or "coming soon" in lowered:
                return "coming_soon"
            if "vorbestell" in lowered or "preorder" in lowered:
                return "preorder"
            if "auf lager" in lowered or "verfügbar" in lowered or "verfugbar" in lowered:
                return "in_stock"

        return None

    def _derive_sale_state(
        self,
        price_amount: str | None,
        price_label: str | None,
        availability_status: str | None,
    ) -> str | None:
        if price_amount is not None:
            return "for_sale"

        if price_label:
            lowered = price_label.lower()
            if "verkauf startet bald" in lowered or "coming soon" in lowered:
                return "coming_soon"

        if availability_status:
            return availability_status

        return None

    def _extract_body_text(self, root) -> str:
        parts = []
        seen = set()

        for selector in [
            ".product-headline",
            ".shortdesc",
            ".delivery-status",
            ".info-wrapper",
            ".delivery-info-wrapper",
            ".product-sku",
            ".product-category",
            ".product-manufacturer",
        ]:
            for el in root.select(selector):
                text = self._clean_text(el.get_text(" ", strip=True))
                if text and text not in seen:
                    seen.add(text)
                    parts.append(text)

        if not parts:
            text = self._clean_text(root.get_text(" ", strip=True)) or ""
            return text[:1200]

        return (self._clean_text(" ".join(parts)) or "")[:1200]