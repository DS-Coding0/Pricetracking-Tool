from bs4 import BeautifulSoup
import logging

logger = logging.getLogger("price_tracker")


def is_blocked_page(html: str) -> bool:
    if not html:
        logger.debug("Blocked check: empty html => blocked")
        return True

    html_lower = html.lower()

    strong_block_markers = [
        "pardon our interruption",
        "request unsuccessful. incapsula incident id",
        "_incapsula_resource",
        "visid_incap_",
        "incap_ses_",
        "access denied",
        "error code: 1020",
        "attention required",
        "cf-chl-",
        "checking your browser",
        "verify you are human",
        "verify you're human",
        "your request has been blocked",
        "website is using a security service",
        "blocked due to unusual activity",
        "automated access",
        "bot protection",
        "px-captcha",
        "datadome",
        "/captcha/",
    ]

    normal_page_markers = [
        "<header",
        "<nav",
        "<main",
        "<footer",
        "warenkorb",
        "mein konto",
        "wunschzettel",
        "wishlist",
        "breadcrumb",
        "search-wrapper",
        "navbar",
        "product-title",
        "price_wrapper",
        "delivery-status",
        'itemprop="price"',
        'itemprop="availability"',
        'itemtype="https://schema.org/product"',
        'itemtype="http://schema.org/product"',
    ]

    strong_hits = [marker for marker in strong_block_markers if marker in html_lower]
    normal_hits = [marker for marker in normal_page_markers if marker in html_lower]

    logger.debug(
        "Blocked check: strong_hits=%s normal_hits=%s html_len=%s",
        strong_hits,
        normal_hits,
        len(html),
    )

    # Wenn klar eine normale Shop-/Produktseite erkennbar ist, nicht blocken.
    if len(normal_hits) >= 3:
        logger.debug("Blocked check result: False (normal page markers present)")
        return False

    # Einzelnes 'captcha' ist zu unscharf und deshalb absichtlich NICHT mehr ausreichend.
    # Geblockt wird nur bei echten starken Markern.
    if strong_hits:
        logger.debug("Blocked check result: True (strong block markers present)")
        return True

    logger.debug("Blocked check result: False (no strong block markers)")
    return False


def clean_soup(soup: BeautifulSoup):
    selectors_to_remove = [
        "script",
        "style",
        "noscript",
        "svg",
        "header",
        "footer",
        "nav",
        "aside",
        "#onetrust-banner-sdk",
        "#onetrust-consent-sdk",
        ".cookie-banner",
        ".cookies-banner",
        ".cc-window",
        "[id*='cookie']",
        "[class*='cookie']",
        "[class*='consent']",
        "[id*='consent']",
    ]

    for selector in selectors_to_remove:
        for el in soup.select(selector):
            el.decompose()

    return soup