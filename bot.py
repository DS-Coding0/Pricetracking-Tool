import json
import datetime
from pathlib import Path
from urllib.parse import urlparse

import discord
import requests
from bs4 import BeautifulSoup
from discord import app_commands
from discord.ext import commands, tasks
from playwright.async_api import async_playwright

import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OWNER_USER_ID_RAW = os.getenv("OWNER_USER_ID")
GUILD_ID_RAW = os.getenv("GUILD_ID")

if not DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN fehlt in der .env")

if not OWNER_USER_ID_RAW:
    raise RuntimeError("OWNER_USER_ID fehlt in der .env")

if not GUILD_ID_RAW:
    raise RuntimeError("GUILD_ID fehlt in der .env")

try:
    OWNER_USER_ID = int(OWNER_USER_ID_RAW)
except ValueError:
    raise RuntimeError("OWNER_USER_ID muss eine gueltige Integer-ID sein")

try:
    GUILD_ID = int(GUILD_ID_RAW)
except ValueError:
    raise RuntimeError("GUILD_ID muss eine gueltige Integer-ID sein")


WATCHLIST_FILE = Path("watchlist.json")
SNAPSHOT_FILE = Path("snapshot.json")
CONFIG_FILE = Path("config.json")

CHECK_INTERVAL_MINUTES = 10


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def is_owner_user(interaction: discord.Interaction) -> bool:
    return interaction.user.id == OWNER_USER_ID

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default
    return default


def save_json(path: Path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=4),
        encoding="utf-8"
    )


def load_watchlist():
    return load_json(WATCHLIST_FILE, [])


def save_watchlist(watchlist):
    save_json(WATCHLIST_FILE, watchlist)


def load_snapshots():
    return load_json(SNAPSHOT_FILE, {})


def save_snapshots(snapshots):
    save_json(SNAPSHOT_FILE, snapshots)


def load_config():
    return load_json(CONFIG_FILE, {
        "notification_channel_id": None
    })


def save_config(config):
    save_json(CONFIG_FILE, config)


def normalize_url(url):
    return url.split("?")[0].rstrip("/")


def is_shopify_product_url(url):
    parsed = urlparse(url)
    return "/products/" in parsed.path


def build_shopify_product_json_url(url):
    return f"{normalize_url(url)}.js"


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


def extract_html_data(html, url, title_from_page=None):
    if html is None or is_blocked_page(html):
        return None

    soup = BeautifulSoup(html, "html.parser")
    soup = clean_soup(soup)

    price = None
    availability = None
    title = title_from_page

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

    title_selectors = [
        "h1.card-title.col-md-10",
        "h1.card-title",
        "h1.product-title",
        "h1.product-name",
        ".card-title.col-md-10",
        ".card-title",
        ".product-title",
        ".product-name",
    ]

    if not title:
        for selector in title_selectors:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(" ", strip=True)
                if text:
                    title = text
                    break

    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

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

    body_text = " ".join(soup.get_text(" ", strip=True).split())[:1200]

    return {
        "source": "html_fallback",
        "url": normalize_url(url),
        "title": title,
        "price": price,
        "availability": availability,
        "body_text": body_text,
    }


async def extract_relevant_data(url):
    if is_shopify_product_url(url):
        product_json = fetch_shopify_product_json(url)
        if product_json:
            data = extract_shopify_data(product_json, url)
            if data:
                return data

    page_data = await fetch_page_with_playwright(url)
    if not page_data:
        return None

    html = page_data.get("html")
    title_from_page = page_data.get("title_from_page")

    return extract_html_data(html, url, title_from_page=title_from_page)


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


def stringify_value(value):
    if value is None:
        return "None"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
        return text[:900] + "..." if len(text) > 900 else text
    return str(value)


TEST_GUILD = discord.Object(id=GUILD_ID)

class PriceTrackerBot(commands.Bot):
    async def setup_hook(self):
        self.tree.copy_global_to(guild=TEST_GUILD)
        synced = await self.tree.sync(guild=TEST_GUILD)
        print(f"{len(synced)} Slash-Commands fuer Guild {GUILD_ID} synchronisiert.")

intents = discord.Intents.default()
bot = PriceTrackerBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot online als {bot.user}")
    if not background_checker.is_running():
        background_checker.start()


async def get_notification_channel():
    config = load_config()
    channel_id = config.get("notification_channel_id")

    if not channel_id:
        return None

    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(channel_id)
    except Exception as e:
        print(f"[FEHLER] Kanal konnte nicht geladen werden: {e}")
        return None

def safe_embed_value(value, fallback="Unbekannt", max_len=1024):
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return text[:max_len]

async def send_change_message(url, old_data, new_data):
    channel = await get_notification_channel()
    if channel is None:
        return

    changes = format_change(old_data, new_data)

    embed = discord.Embed(
        title="🔔 Produktaenderung erkannt",
        description=f"[Produkt oeffnen]({url})",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    embed.add_field(
        name="Titel",
        value=safe_embed_value(new_data.get("title")),
        inline=False
    )

    old_price = stringify_value(old_data.get("price")) if old_data else "None"
    new_price = stringify_value(new_data.get("price"))
    embed.add_field(
        name="Preis",
        value=f"Alt: `{old_price}`\nNeu: `{new_price}`",
        inline=True
    )

    old_availability = stringify_value(old_data.get("availability")) if old_data else "None"
    new_availability = stringify_value(new_data.get("availability"))
    embed.add_field(
        name="Verfuegbarkeit",
        value=f"Alt: `{old_availability}`\nNeu: `{new_availability}`",
        inline=True
    )

    relevant_change_lines = []
    ignored_keys = {"body_text"}

    for key, value in changes.items():
        if key in ignored_keys:
            continue
        if key in {"price", "availability", "title"}:
            continue

        old_val = stringify_value(value["old"])
        new_val = stringify_value(value["new"])
        relevant_change_lines.append(
            f"**{key}**\nAlt: `{old_val}`\nNeu: `{new_val}`"
        )

    if relevant_change_lines:
        details = "\n\n".join(relevant_change_lines)
        embed.add_field(
            name="Weitere Aenderungen",
            value=details[:1024],
            inline=False
        )

    embed.set_footer(text="Price Tracker Bot")

    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[FEHLER] Nachricht konnte nicht gesendet werden: {e}")


async def check_url(url, snapshots):
    current_data = await extract_relevant_data(url)

    if current_data is None:
        print(f"[FEHLER] Keine verwertbaren Daten fuer {url}")
        return

    old_data = snapshots.get(url)

    if old_data is None:
        snapshots[url] = current_data
        print(f"[ERSTAUFRUF] Snapshot gespeichert: {url}")
        return

    if current_data != old_data:
        print(f"[AENDERUNG] {url}")
        await send_change_message(url, old_data, current_data)
        snapshots[url] = current_data
    else:
        print(f"[OK] Keine Aenderung: {url}")


async def run_all_checks():
    print("Pruefung gestartet...")
    watchlist = load_watchlist()
    snapshots = load_snapshots()
    
    for url in watchlist:
        try:
            await check_url(url, snapshots)
        except Exception as e:
            print(f"[FEHLER] {url}: {e}")

    save_snapshots(snapshots)
    print("Pruefung beendet.\n")


@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def background_checker():
    await run_all_checks()


@background_checker.before_loop
async def before_background_checker():
    await bot.wait_until_ready()



@bot.tree.command(name="add", description="Fuegt einen neuen Produktlink zur Watchlist hinzu.")
@app_commands.describe(url="Produktlink, der ueberwacht werden soll")
async def add_product(interaction: discord.Interaction, url: str):
    url = normalize_url(url)
    watchlist = load_watchlist()

    if url in watchlist:
        await interaction.response.send_message(
            "Dieser Link ist bereits in der Watchlist.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    data = await extract_relevant_data(url)
    if data is None:
        await interaction.followup.send(
            "Die Seite konnte nicht gelesen werden oder ist blockiert.",
            ephemeral=True
        )
        return

    watchlist.append(url)
    save_watchlist(watchlist)

    snapshots = load_snapshots()
    snapshots[url] = data
    save_snapshots(snapshots)

    await interaction.followup.send(
        f"Produktlink hinzugefuegt:\n{url}",
        ephemeral=True
    )


@bot.tree.command(name="remove", description="Entfernt einen Produktlink aus der Watchlist.")
@app_commands.describe(url="Produktlink, der entfernt werden soll")
async def remove_product(interaction: discord.Interaction, url: str):
    url = normalize_url(url)
    watchlist = load_watchlist()

    if url not in watchlist:
        await interaction.response.send_message(
            "Dieser Link ist nicht in der Watchlist.",
            ephemeral=True
        )
        return

    watchlist.remove(url)
    save_watchlist(watchlist)

    snapshots = load_snapshots()
    if url in snapshots:
        del snapshots[url]
        save_snapshots(snapshots)

    await interaction.response.send_message(
        f"Produktlink entfernt:\n{url}",
        ephemeral=True
    )


@bot.tree.command(name="list", description="Zeigt alle ueberwachten Produktlinks.")
async def list_products(interaction: discord.Interaction):
    watchlist = load_watchlist()

    if not watchlist:
        await interaction.response.send_message(
            "Die Watchlist ist leer.",
            ephemeral=True
        )
        return

    text = "\n".join(f"- {url}" for url in watchlist)
    if len(text) > 1900:
        text = text[:1900] + "\n..."

    await interaction.response.send_message(
        f"**Watchlist:**\n{text}",
        ephemeral=True
    )


@bot.tree.command(name="setchannel", description="Setzt den Kanal fuer oeffentliche Aenderungsbenachrichtigungen.")
@app_commands.check(is_owner_user)
@app_commands.describe(channel="Discord-Kanal fuer Benachrichtigungen")
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    config["notification_channel_id"] = channel.id
    save_config(config)

    await interaction.response.send_message(
        f"Benachrichtigungskanal gesetzt auf {channel.mention}",
        ephemeral=True
    )


@bot.tree.command(name="checknow", description="Startet sofort eine manuelle Pruefung.")
async def check_now(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await run_all_checks()
    await interaction.followup.send(
        "Pruefung abgeschlossen.",
        ephemeral=True
    )

@bot.tree.command(name="help", description="Zeigt alle wichtigen Befehle des Bots an.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Price Tracker Hilfe",
        description="Hier findest du die wichtigsten Slash-Commands des Bots.",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    embed.add_field(
        name="/add <url>",
        value="Fuegt einen neuen Produktlink zur Watchlist hinzu und speichert direkt den ersten Snapshot.",
        inline=False
    )

    embed.add_field(
        name="/remove <url>",
        value="Entfernt einen Produktlink aus der Watchlist und loescht den zugehoerigen Snapshot.",
        inline=False
    )

    embed.add_field(
        name="/list",
        value="Zeigt alle aktuell ueberwachten Produktlinks an.",
        inline=False
    )

    embed.add_field(
        name="/setchannel <kanal>",
        value="Legt fest, in welchen Kanal oeffentliche Aenderungsbenachrichtigungen gesendet werden.",
        inline=False
    )

    embed.add_field(
        name="/checknow",
        value="Startet sofort eine manuelle Pruefung aller Produkte in der Watchlist.",
        inline=False
    )

    embed.add_field(
        name="/help",
        value="Zeigt diese Hilfe an.",
        inline=False
    )

    embed.add_field(
        name="Hinweis",
        value="Slash-Command-Antworten sind nur fuer dich sichtbar, echte Produktaenderungen werden oeffentlich in den gesetzten Kanal gepostet.",
        inline=False
    )

    embed.set_footer(text="Price Tracker Bot")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.CheckFailure):
        if interaction.response.is_done():
            await interaction.followup.send(
                "Du darfst diesen Befehl nicht verwenden.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Du darfst diesen Befehl nicht verwenden.",
                ephemeral=True
            )
        return

    print(f"[APP_COMMAND_ERROR] {error}")

    if interaction.response.is_done():
        await interaction.followup.send(
            "Beim Ausfuehren des Befehls ist ein Fehler aufgetreten.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "Beim Ausfuehren des Befehls ist ein Fehler aufgetreten.",
            ephemeral=True
        )

bot.run(DISCORD_BOT_TOKEN)