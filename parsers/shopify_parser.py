from urllib.parse import urlparse

from parsers.base import BaseParser
from utils.helpers import normalize_url
from utils.http import fetch_json_with_retry


class ShopifyParser(BaseParser):
    name = "shopify"

    def can_handle(self, url: str, html: str | None = None) -> bool:
        parsed = urlparse(url)
        return "/products/" in parsed.path

    async def parse(self, url: str, session, html: str | None = None, title_from_page: str | None = None):
        json_url = f"{normalize_url(url)}.js"
        product_json = await fetch_json_with_retry(session, json_url)
        if not product_json:
            return None

        variants = product_json.get("variants", [])
        product_available = product_json.get("available")
        first_variant = variants[0] if variants else {}

        variant_data = []
        for variant in variants:
            variant_data.append({
                "id": variant.get("id"),
                "title": variant.get("title"),
                "price": variant.get("price"),
                "available": variant.get("available"),
                "sku": variant.get("sku"),
            })

        return {
            "source": "shopify_json",
            "url": normalize_url(url),
            "title": product_json.get("title", ""),
            "handle": product_json.get("handle", ""),
            "vendor": product_json.get("vendor", ""),
            "product_type": product_json.get("type", ""),
            "price": first_variant.get("price"),
            "compare_at_price": first_variant.get("compare_at_price"),
            "price_min": product_json.get("price_min"),
            "price_max": product_json.get("price_max"),
            "available": product_available,
            "availability": "available" if product_available else "sold_out",
            "variant_count": len(variant_data),
            "variants": variant_data,
        }