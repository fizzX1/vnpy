"""
Global setting of the trading platform.
"""

from logging import CRITICAL
from typing import Dict, Any
from tzlocal import get_localzone_name

from .utility import load_json


SETTINGS: Dict[str, Any] = {
    "font.family": "Monaco",
    "font.size": 12,

    "log.active": True,
    "log.level": CRITICAL,
    "log.console": True,
    "log.file": True,

    "email.server": "smtp.qq.com",
    "email.port": 465,
    "email.username": "",
    "email.password": "",
    "email.sender": "",
    "email.receiver": "",

    "datafeed.name": "tushare",
    "datafeed.username": "token",
    "datafeed.password": "502bcbdbac29edf1c42ed84d5f9bd24d63af6631919820366f53e5d4",

    "database.timezone": get_localzone_name(),
    "database.name": "mongodb",
    "database.database": "admin",
    "database.host": "homes.fizzx.top",
    "database.port": 27017,
    "database.user": "root",
    "database.password": "sf83ndfkwjm2#dnBb"
}


# Load global setting from json file.
SETTING_FILENAME: str = "vt_setting.json"
SETTINGS.update(load_json(SETTING_FILENAME))


def get_settings(prefix: str = "") -> Dict[str, Any]:
    prefix_length: int = len(prefix)
    settings = {k[prefix_length:]: v for k, v in SETTINGS.items() if k.startswith(prefix)}
    return settings
