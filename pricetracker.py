import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from playwright.sync_api import sync_playwright


WATCHLIST = [
    "https://tcgviert.com/products/pokemon-tcg-gem-pack-vol-5-cbb5c-display-chn",
    "https://www.cardbuddys.de/home/produkte/pokemon-tcg/boxen/16969/mega-entwicklungen-wachsendes-chaos-top-trainer-box-de",
]

SNAPSHOT_FILE = Path("snapshot.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def load_snapshots():
    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    return {}


def save_snapshots(snapshots):
    SNAPSHOT_FILE.write_text(
        json.dumps(snapshots, ensure_ascii=False, indent=4),
        encoding="utf-8"
    )


def normalize_url(url):
    return url.split("?")[0].rstrip("/")


def is_shopify_product_url(url):
    parsed = urlparse(url)
    return "/products/" in parsed.path


def build_shopify_product_json_url(url):
    clean_url = normalize_url(url)
    return f"{clean_url}.js"


def is_blocked_page(html: str) -> bool:
    if not html:
        return True

    markers = [
        "Pardon Our Interruption",
        "Request unsuccessful. Incapsula incident ID",
        "_Incapsula_Resource",
        "visid_incap_",
        "incap_ses_",
        "Access denied",
        "captcha",
    ]
    html_lower = html.lower()
    return any(marker.lower() in html_lower for marker in markers)


def fetch_shopify_product_json(url):
    try:
        json_url = build_shopify_product_json_url(url)
        response = requests.get(json_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None
    except ValueError:
        return None


def fetch_page_with_playwright(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                locale="de-DE",
                user_agent=HEADERS["User-Agent"]
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def clean_soup(soup):
    selectors_to_remove = [
        "script",
        "style",
        "noscript",
        "svg",
        "header",
        "footer",
        "nav",
        "aside",
        "form[action*='cookie']",
        "#shopify-section-header",
        "#shopify-section-footer",
        "#onetrust-banner-sdk",
        "#onetrust-consent-sdk",
        ".cookie-banner",
        ".cookies-banner",
        ".cc-window",
        ".needsclick",
        "[id*='cookie']",
        "[class*='cookie']",
        "[class*='consent']",
        "[id*='consent']",
        "[aria-label*='cookie']",
    ]

    for selector in selectors_to_remove:
        for el in soup.select(selector):
            el.decompose()

    return soup


def extract_shopify_data(product_json, url):
    if not product_json:
        return None

    variants = product_json.get("variants", [])
    product_available = product_json.get("available")

    variant_data = []
    for variant in variants:
        variant_data.append({
            "id": variant.get("id"),
            "title": variant.get("title"),
            "price": variant.get("price"),
            "available": variant.get("available"),
            "sku": variant.get("sku"),
        })

    first_variant = variants[0] if variants else {}

    price = first_variant.get("price")
    compare_at_price = first_variant.get("compare_at_price")
    availability = "available" if product_available else "sold_out"

    return {
        "source": "shopify_json",
        "url": normalize_url(url),
        "title": product_json.get("title", ""),
        "handle": product_json.get("handle", ""),
        "vendor": product_json.get("vendor", ""),
        "product_type": product_json.get("type", ""),
        "tags": product_json.get("tags", []),
        "price": price,
        "compare_at_price": compare_at_price,
        "price_min": product_json.get("price_min"),
        "price_max": product_json.get("price_max"),
        "available": product_available,
        "availability": availability,
        "variant_count": len(variant_data),
        "variants": variant_data,
    }


def extract_html_data(html, url):
    if html is None or is_blocked_page(html):
        return None

    soup = BeautifulSoup(html, "html.parser")
    soup = clean_soup(soup)

    title = soup.title.get_text(strip=True) if soup.title else ""

    price = None
    availability = None

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

    for selector in price_selectors:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(" ", strip=True)
            if text:
                price = text
                break

    for selector in availability_selectors:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(" ", strip=True)
            if text:
                availability = text
                break

    body_text = soup.get_text(" ", strip=True)
    body_text = " ".join(body_text.split())[:1500]

    return {
        "source": "html_fallback",
        "url": normalize_url(url),
        "title": title,
        "price": price,
        "availability": availability,
        "body_text": body_text,
    }


def extract_relevant_data(url):
    if is_shopify_product_url(url):
        product_json = fetch_shopify_product_json(url)
        if product_json:
            data = extract_shopify_data(product_json, url)
            if data:
                return data

    html = fetch_page_with_playwright(url)
    return extract_html_data(html, url)


def format_change(old_data, new_data):
    changed = {}

    old_keys = set(old_data.keys()) if old_data else set()
    new_keys = set(new_data.keys()) if new_data else set()

    for key in sorted(old_keys | new_keys):
        old_value = old_data.get(key) if old_data else None
        new_value = new_data.get(key) if new_data else None
        if old_value != new_value:
            changed[key] = {
                "old": old_value,
                "new": new_value
            }

    return changed


def check_url(url, snapshots):
    try:
        current_data = extract_relevant_data(url)

        if current_data is None:
            print(f"[FEHLER] Keine verwertbaren Daten fuer {url}")
            return

        old_data = snapshots.get(url)

        if old_data is None:
            snapshots[url] = current_data
            print(f"[ERSTAUFRUF] Snapshot gespeichert: {url}")
            print(f"  Titel: {current_data.get('title')}")
            print(f"  Preis: {current_data.get('price')}")
            print(f"  Verfuegbarkeit: {current_data.get('availability')}")
            return

        if current_data != old_data:
            print(f"[AENDERUNG] {url}")
            changes = format_change(old_data, current_data)

            for key, value in changes.items():
                print(f"  {key}:")
                print(f"    Alt: {value['old']}")
                print(f"    Neu: {value['new']}")

            snapshots[url] = current_data
        else:
            print(f"[OK] Keine Aenderung: {url}")

    except Exception as e:
        print(f"[FEHLER] {url}: {e}")


def run_all_checks():
    print("Pruefung gestartet...")
    snapshots = load_snapshots()

    for url in WATCHLIST:
        check_url(url, snapshots)

    save_snapshots(snapshots)
    print("Pruefung beendet.\n")


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_all_checks,
        "interval",
        minutes=10,
        id="pricechecker_monitor",
        max_instances=1
    )
    scheduler.start()

    run_all_checks()

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()