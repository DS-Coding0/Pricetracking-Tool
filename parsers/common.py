from bs4 import BeautifulSoup


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