import json
from pathlib import Path

from utils.logger import logger


WATCHLIST_FILE = Path("data/watchlist.json")
SNAPSHOT_FILE = Path("data/snapshot.json")
CONFIG_FILE = Path("data/config.json")


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("JSON-Datei konnte nicht gelesen werden: %s", path)
            return default
    return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
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
    config = load_json(CONFIG_FILE, {"notification_channel_ids": []})

    if "notification_channel_ids" not in config:
        legacy_channel_id = config.get("notification_channel_id")
        if legacy_channel_id:
            config["notification_channel_ids"] = [legacy_channel_id]
        else:
            config["notification_channel_ids"] = []

    return config


def save_config(config):
    save_json(CONFIG_FILE, config)