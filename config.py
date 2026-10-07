import json
import os
from pathlib import Path


def load_credentials(path=None, environ=None):
    environ = os.environ if environ is None else environ
    names = ("SITE", "EMAIL", "TOKEN")
    local = {}
    if any(f"JIRA_{name}" not in environ for name in names):
        path = Path(path) if path is not None else Path(__file__).parent / ".jira-credentials.json"
        if path.exists():
            with path.open("r", encoding="utf-8-sig") as stream:
                try:
                    local = json.load(stream)
                except json.JSONDecodeError:
                    raise ValueError("Local credentials file is not valid JSON") from None
            if not isinstance(local, dict):
                raise ValueError("Local credentials file must contain a JSON object")
    values = {}
    for name in names:
        value = environ.get(f"JIRA_{name}", local.get(name, ""))
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        values[name] = value.strip()
    return values


_credentials = load_credentials()
SITE = _credentials["SITE"]
EMAIL = _credentials["EMAIL"]
TOKEN = _credentials["TOKEN"]

SNAPSHOT_VERSION = "6"
REQUEST_TIMEOUT = 60
MAX_RETRY_ATTEMPTS = 6
DEFAULT_PAGE_SIZE = 100
GOVERNANCE_MAX_WORKERS = 4


def validate_config():
    for name, value in {"EMAIL": EMAIL, "TOKEN": TOKEN, "SITE": SITE}.items():
        if not value:
            raise ValueError(f"{name} is empty; set JIRA_{name} or .jira-credentials.json")
    if not SITE.startswith("https://"):
        raise ValueError("SITE must start with https:// to protect credentials in transit")
