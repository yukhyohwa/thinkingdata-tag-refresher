"""
Configuration — environment variables, tag list, constants.
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()

TA_URL      = os.getenv("TA_URL",  "https://ss-web.5xgames.com/")
TA_USER     = os.getenv("TA_USER", "")
TA_PASS     = os.getenv("TA_PASS", "")
TAG_URL     = os.getenv("TAG_URL", "https://ss-web.5xgames.com/#/tag/tag/1?currentProjectId=23")
GROUP_URL   = os.getenv("GROUP_URL", "https://ss-web.5xgames.com/#/group/userGroup/all?currentProjectId=23")
SESSION_DIR = os.path.abspath(os.getenv("SESSION_DIR", "./ta_session"))

# Tags to refresh, in order
TAGS_TO_REFRESH = [
    "fixed_deviceid",
    "fixed_country",
    "fixed_os",
    "fixed_affcode",
    "fixed_regdate",
    "fixed_ip",
    "fixed_zone",
]

# Groups to refresh, in order
GROUPS_TO_REFRESH = [
    "is_water",
]

# Milliseconds to wait after each successful refresh before moving to the next tag
WAIT_AFTER_REFRESH_MS = int(os.getenv("WAIT_AFTER_REFRESH", "5")) * 1000

# Minutes to wait between tag refresh phase and group refresh phase
WAIT_BETWEEN_PHASES_MIN = float(os.getenv("WAIT_BETWEEN_PHASES_MIN", "2"))

os.makedirs(SESSION_DIR, exist_ok=True)


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    safe_msg = msg.encode("gbk", errors="replace").decode("gbk")
    print(f"[{ts}] {safe_msg}", flush=True)
