import json

from utils.config import OWNER_USER_ID


def is_owner_user(interaction) -> bool:
    return interaction.user.id == OWNER_USER_ID


def normalize_url(url):
    return url.split("?")[0].rstrip("/")


def format_change(old_data, new_data):
    changed = {}
    old_keys = set(old_data.keys()) if old_data else set()
    new_keys = set(new_data.keys()) if new_data else set()

    for key in sorted(old_keys | new_keys):
        old_value = old_data.get(key) if old_data else None
        new_value = new_data.get(key) if new_data else None
        if old_value != new_value:
            changed[key] = {"old": old_value, "new": new_value}

    return changed


def stringify_value(value):
    if value is None:
        return "None"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
        return text[:900] + "..." if len(text) > 900 else text
    return str(value)


def safe_embed_value(value, fallback="Unbekannt", max_len=1024):
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return text[:max_len]