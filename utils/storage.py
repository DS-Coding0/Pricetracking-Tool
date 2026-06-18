import json
from pathlib import Path

from utils.logger import logger


WATCHLIST_FILE = Path("watchlist.json")
SNAPSHOT_FILE = Path("snapshot.json")
CONFIG_FILE = Path("config.json")


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("JSON-Datei konnte nicht gelesen werden: %s", path)
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
    return load_json(CONFIG_FILE, {"notification_channel_id": None})


def save_config(config):
    save_json(CONFIG_FILE, config)