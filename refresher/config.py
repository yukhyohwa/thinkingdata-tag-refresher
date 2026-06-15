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
TAG_URL     = os.getenv("TAG_URL", "https://ss-web.5xgames.com/#/tag/tag/1?currentProjectId=13")
SESSION_DIR = os.path.abspath(os.getenv("SESSION_DIR", "./ta_session"))

# Tags to refresh, in order
TAGS_TO_REFRESH = [
    "fixed_os",
    "fixed_country",
    "fixed_regdate",
    "fixed_serverid",
]

# Milliseconds to wait after each successful refresh before moving to the next tag
WAIT_AFTER_REFRESH_MS = int(os.getenv("WAIT_AFTER_REFRESH", "5")) * 1000

os.makedirs(SESSION_DIR, exist_ok=True)


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    safe_msg = msg.encode("gbk", errors="replace").decode("gbk")
    print(f"[{ts}] {safe_msg}", flush=True)
