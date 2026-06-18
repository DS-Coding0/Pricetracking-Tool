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

CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}