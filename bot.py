import datetime
import json

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.config import (
    CHECK_INTERVAL_MINUTES,
    DISCORD_BOT_TOKEN,
    GUILD_ID,
    OWNER_USER_ID,
)
from utils.helpers import (
    format_change,
    is_owner_user,
    normalize_url,
    safe_embed_value,
    stringify_value,
)
from utils.logger import logger
from utils.storage import (
    load_config,
    load_snapshots,
    load_watchlist,
    save_config,
    save_snapshots,
    save_watchlist,
)
from parsers.registry import parser_registry


TEST_GUILD = discord.Object(id=GUILD_ID)


class PriceTrackerBot(commands.Bot):
    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        self.tree.copy_global_to(guild=TEST_GUILD)
        synced = await self.tree.sync(guild=TEST_GUILD)
        logger.info("%s Slash-Commands fuer Guild %s synchronisiert.", len(synced), GUILD_ID)

    async def close(self):
        if hasattr(self, "http_session") and self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()


intents = discord.Intents.default()
bot = PriceTrackerBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info("Bot online als %s", bot.user)
    if not background_checker.is_running():
        background_checker.start()


async def extract_relevant_data(url, session):
    return await parser_registry.extract(url, session)


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
        logger.error("Kanal konnte nicht geladen werden: %s", e)
        return None


async def send_change_message(url, old_data, new_data):
    channel = await get_notification_channel()
    if channel is None:
        logger.warning("Kein Benachrichtigungskanal gesetzt.")
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
        if key in ignored_keys or key in {"price", "availability", "title"}:
            continue
        old_val = stringify_value(value["old"])
        new_val = stringify_value(value["new"])
        relevant_change_lines.append(f"**{key}**\nAlt: `{old_val}`\nNeu: `{new_val}`")

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
        logger.info("Aenderungsbenachrichtigung gesendet fuer %s", url)
    except Exception as e:
        logger.error("Nachricht konnte nicht gesendet werden: %s", e)


async def check_url(url, snapshots):
    current_data = await extract_relevant_data(url, bot.http_session)

    if current_data is None:
        logger.error("Keine verwertbaren Daten fuer %s", url)
        return

    old_data = snapshots.get(url)

    if old_data is None:
        snapshots[url] = current_data
        logger.info("ERSTAUFRUF Snapshot gespeichert: %s", url)
        return

    if current_data != old_data:
        logger.info("AENDERUNG erkannt: %s", url)
        await send_change_message(url, old_data, current_data)
        snapshots[url] = current_data
    else:
        logger.info("Keine Aenderung: %s", url)


async def run_all_checks():
    logger.info("Pruefung gestartet...")
    watchlist = load_watchlist()
    snapshots = load_snapshots()

    for url in watchlist:
        try:
            await check_url(url, snapshots)
        except Exception as e:
            logger.exception("Fehler bei %s: %s", url, e)

    save_snapshots(snapshots)
    logger.info("Pruefung beendet.")


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

    data = await extract_relevant_data(url, bot.http_session)
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

    logger.info("Produktlink hinzugefuegt: %s", url)
    await interaction.followup.send(f"Produktlink hinzugefuegt:\n{url}", ephemeral=True)


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

    logger.info("Produktlink entfernt: %s", url)
    await interaction.response.send_message(f"Produktlink entfernt:\n{url}", ephemeral=True)


@bot.tree.command(name="list", description="Zeigt alle ueberwachten Produktlinks.")
async def list_products(interaction: discord.Interaction):
    watchlist = load_watchlist()

    if not watchlist:
        await interaction.response.send_message("Die Watchlist ist leer.", ephemeral=True)
        return

    text = "\n".join(f"- {url}" for url in watchlist)
    if len(text) > 1900:
        text = text[:1900] + "\n..."

    await interaction.response.send_message(f"**Watchlist:**\n{text}", ephemeral=True)


@bot.tree.command(name="setchannel", description="Setzt den Kanal fuer oeffentliche Aenderungsbenachrichtigungen.")
@app_commands.check(is_owner_user)
@app_commands.describe(channel="Discord-Kanal fuer Benachrichtigungen")
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    config["notification_channel_id"] = channel.id
    save_config(config)

    logger.info("Benachrichtigungskanal gesetzt: %s", channel.id)
    await interaction.response.send_message(
        f"Benachrichtigungskanal gesetzt auf {channel.mention}",
        ephemeral=True
    )


@bot.tree.command(name="checknow", description="Startet sofort eine manuelle Pruefung.")
async def check_now(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await run_all_checks()
    await interaction.followup.send("Pruefung abgeschlossen.", ephemeral=True)


@bot.tree.command(name="help", description="Zeigt alle wichtigen Befehle des Bots an.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Price Tracker Hilfe",
        description="Hier findest du die wichtigsten Slash-Commands des Bots.",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    embed.add_field(name="/add <url>", value="Fuegt einen neuen Produktlink zur Watchlist hinzu und speichert direkt den ersten Snapshot.", inline=False)
    embed.add_field(name="/remove <url>", value="Entfernt einen Produktlink aus der Watchlist und loescht den zugehoerigen Snapshot.", inline=False)
    embed.add_field(name="/list", value="Zeigt alle aktuell ueberwachten Produktlinks an.", inline=False)
    embed.add_field(name="/setchannel <kanal>", value="Legt fest, in welchen Kanal oeffentliche Aenderungsbenachrichtigungen gesendet werden.", inline=False)
    embed.add_field(name="/checknow", value="Startet sofort eine manuelle Pruefung aller Produkte in der Watchlist.", inline=False)
    embed.add_field(name="/help", value="Zeigt diese Hilfe an.", inline=False)
    embed.add_field(name="Hinweis", value="Slash-Command-Antworten sind nur fuer dich sichtbar, echte Produktaenderungen werden oeffentlich in den gesetzten Kanal gepostet.", inline=False)
    embed.set_footer(text="Price Tracker Bot")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.CheckFailure):
        if interaction.response.is_done():
            await interaction.followup.send("Du darfst diesen Befehl nicht verwenden.", ephemeral=True)
        else:
            await interaction.response.send_message("Du darfst diesen Befehl nicht verwenden.", ephemeral=True)
        return

    logger.exception("APP_COMMAND_ERROR: %s", error)

    if interaction.response.is_done():
        await interaction.followup.send("Beim Ausfuehren des Befehls ist ein Fehler aufgetreten.", ephemeral=True)
    else:
        await interaction.response.send_message("Beim Ausfuehren des Befehls ist ein Fehler aufgetreten.", ephemeral=True)


bot.run(DISCORD_BOT_TOKEN)