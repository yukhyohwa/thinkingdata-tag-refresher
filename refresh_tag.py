"""
fivecross-ta-tag-refresher
==========================
Navigates to the ThinkingData tag management page, auto-logs in if needed
(using a persistent browser session so subsequent runs stay logged in),
then clicks the tag refresh (刷新) button.

Usage:
    python refresh_tag.py          # headless (for scheduled tasks)
    python refresh_tag.py --show   # visible browser (for debugging)
    python refresh_tag.py --login  # force re-login (clears old session first)
"""

import os
import sys
import time
import shutil
import argparse
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

TA_URL      = os.getenv("TA_URL",      "http://8.211.141.76:8993/")
TA_USER     = os.getenv("TA_USER",     "")
TA_PASS     = os.getenv("TA_PASS",     "")
TAG_URL     = os.getenv("TAG_URL",     "http://8.211.141.76:8993/#/tag/tag/1?currentProjectId=16")
SESSION_DIR = os.path.abspath(os.getenv("SESSION_DIR", "./ta_session"))

os.makedirs(SESSION_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    # Encode safely for Windows GBK consoles
    safe_msg = msg.encode("gbk", errors="replace").decode("gbk")
    print(f"[{ts}] {safe_msg}", flush=True)


def clear_session():
    """Delete the persistent session so the next launch forces a fresh login."""
    if os.path.exists(SESSION_DIR):
        shutil.rmtree(SESSION_DIR, ignore_errors=True)
    os.makedirs(SESSION_DIR, exist_ok=True)
    log("Session cleared. Will perform fresh login on next run.")


def is_login_page(page) -> bool:
    return (
        "login" in page.url.lower()
        or bool(page.query_selector('input[type="password"]'))
    )


def perform_login(page):
    """Fill in credentials and submit the login form."""
    log("Login page detected — performing auto-login...")

    # Wait for username input
    user_input = page.wait_for_selector(
        'input[placeholder*="Account"], input[placeholder*="Username"], '
        'input[placeholder*="账号"], input[id="username"], input[type="text"]',
        timeout=15000,
    )
    pass_input = page.wait_for_selector(
        'input[placeholder*="Password"], input[placeholder*="密码"], '
        'input[id="password"], input[type="password"]',
        timeout=15000,
    )

    user_input.fill("")
    user_input.type(TA_USER, delay=40)
    pass_input.fill("")
    pass_input.type(TA_PASS, delay=40)

    # Try to tick "remember me / 7天免登录" if present
    try:
        remember = page.query_selector(
            'label:has-text("7"), label:has-text("免登录"), '
            'label:has-text("自动登录"), label:has-text("Remember")'
        )
        if remember:
            remember.click()
        else:
            cb = page.query_selector('input[type="checkbox"]')
            if cb and not cb.is_checked():
                cb.check()
    except Exception:
        pass

    page.wait_for_timeout(800)

    # Click the login button
    clicked = False
    try:
        btn = (
            page.get_by_role("button", name="登录")
            .or_(page.get_by_text("登录", exact=True))
            .first
        )
        if btn.is_visible():
            btn.click()
            clicked = True
    except Exception:
        pass

    if not clicked:
        for sel in ['button:has-text("登录")', ".ant-btn-primary", 'button[type="submit"]']:
            candidate = page.query_selector(sel)
            if candidate and candidate.is_visible():
                candidate.click()
                clicked = True
                break

    # Fallback: press Enter on the password field
    pass_input.focus()
    page.keyboard.press("Enter")

    # Wait for navigation away from login page
    try:
        page.wait_for_url(lambda url: "login" not in url.lower(), timeout=15000)
        log("Login successful!")
    except PlaywrightTimeout:
        # Some builds just reload; wait a bit and check
        page.wait_for_timeout(5000)
        if is_login_page(page):
            raise RuntimeError("Login failed — still on login page after submit.")
        log("Login successful (no URL change detected, but login page gone).")


def click_refresh_button(page) -> bool:
    """
    Find and click the tag refresh button on the tag management page.

    The TA tag page has a refresh icon (circular arrow) as the FIRST button
    in the '操作 (Operations)' column of each tag row in the table.
    The button class is: ant-btn ant-btn-default ant-btn-sm tant-next-button tant-next-button-only-icon

    We click the refresh button for the FIRST tag row.
    Returns True on success, False if the button was not found.
    """
    log("Looking for the refresh button (first row of tag table)...")

    # Strategy 1: First icon-only action button in the table (most reliable)
    # These are the small icon buttons in the 操作 column
    icon_only_selectors = [
        # Icon-only small buttons in the table
        'td .tant-next-button-only-icon:first-child',
        'td .ant-btn-sm.tant-next-button-only-icon',
        '.ant-table-tbody tr:first-child td:last-child button:first-child',
        '.ant-table-tbody tr:first-child .ant-btn:first-child',
        # Any small icon button inside a table cell
        'td.ant-table-cell button.ant-btn-sm',
    ]

    for sel in icon_only_selectors:
        try:
            els = page.query_selector_all(sel)
            # Pick first visible one
            for el in els:
                if el and el.is_visible():
                    cls = el.get_attribute("class") or ""
                    log(f"Found candidate via '{sel}': class='{cls[:60]}'")
                    page.evaluate("el => el.click()", el)
                    log(f"Clicked refresh button via: {sel}")
                    return True
        except Exception as e:
            log(f"Selector '{sel}' failed: {e}")
            continue

    # Strategy 2: All ant-btn-sm buttons — click the first visible one in a table row
    try:
        btn_sels = page.query_selector_all(
            '.ant-table-tbody .ant-btn-sm, .ant-table-tbody .tant-next-button'
        )
        log(f"Found {len(btn_sels)} ant-btn-sm buttons in table.")
        for btn in btn_sels:
            if btn.is_visible():
                cls = btn.get_attribute("class") or ""
                log(f"Clicking first visible table button: class='{cls[:60]}'")
                page.evaluate("el => el.click()", btn)
                return True
    except Exception as e:
        log(f"Strategy 2 failed: {e}")

    # Strategy 3: All anticon elements — pick the first visible one in the table
    try:
        icons = page.query_selector_all('.ant-table-tbody .anticon, .ant-table-tbody [role="img"]')
        log(f"Found {len(icons)} anticons in table.")
        for icon in icons:
            if icon.is_visible():
                cls = icon.get_attribute("class") or ""
                log(f"Clicking first visible table anticon: class='{cls[:60]}'")
                page.evaluate("el => el.click()", icon)
                return True
    except Exception as e:
        log(f"Strategy 3 failed: {e}")

    # Strategy 4: Global anticon-sync or anticon-reload
    try:
        for icon_cls in ['.anticon-sync', '.anticon-reload', '.anticon-redo']:
            icons = page.query_selector_all(icon_cls)
            for icon in icons:
                if icon.is_visible():
                    log(f"Clicking {icon_cls} icon.")
                    page.evaluate("el => el.click()", icon)
                    return True
    except Exception as e:
        log(f"Strategy 4 failed: {e}")

    return False


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def run(headless: bool = True, force_login: bool = False):
    if force_login:
        clear_session()

    with sync_playwright() as p:
        log(f"Launching browser (headless={headless}) ...")
        log(f"Session dir: {SESSION_DIR}")

        context = p.chromium.launch_persistent_context(
            SESSION_DIR,
            headless=headless,
            slow_mo=80,
            permissions=["clipboard-read", "clipboard-write"],
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()

        # ----------------------------------------------------------------
        # Step 1: Navigate to the target tag page
        # ----------------------------------------------------------------
        log(f"Navigating to: {TAG_URL}")
        page.goto(TAG_URL)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass  # continue even if network never goes fully idle (SPA)

        # ----------------------------------------------------------------
        # Step 2: Handle login if required
        # ----------------------------------------------------------------
        if is_login_page(page):
            if not TA_USER or not TA_PASS:
                log("ERROR: Credentials not set. Edit .env and re-run.")
                context.close()
                sys.exit(1)

            perform_login(page)

            # After login, navigate back to the tag page
            log(f"Navigating back to tag page: {TAG_URL}")
            page.goto(TAG_URL)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeout:
                pass
        else:
            log("Existing session detected — skipping login.")

        # ----------------------------------------------------------------
        # Step 3: Wait for the page content to stabilise
        # ----------------------------------------------------------------
        log("Waiting for tag page to load...")
        try:
            # Wait until at least one tag row / card is visible
            page.wait_for_selector(
                ".ant-table-row, .ant-card, .ant-list-item, [class*='tagItem'], [class*='tag-item']",
                timeout=20000,
            )
        except PlaywrightTimeout:
            log("WARNING: Tag list selector not found within timeout; proceeding anyway.")

        page.wait_for_timeout(1500)  # extra settling time for SPA rendering

        # ----------------------------------------------------------------
        # Step 4: Always save screenshot first (helps diagnose issues)
        # ----------------------------------------------------------------
        screenshot_path = os.path.join(os.path.dirname(__file__), "debug_screenshot.png")
        try:
            page.screenshot(path=screenshot_path, full_page=True)
            log(f"Screenshot saved: {screenshot_path}")
        except Exception as e:
            log(f"Screenshot failed: {e}")

        # ----------------------------------------------------------------
        # Step 5: Click the refresh button
        # ----------------------------------------------------------------
        success = click_refresh_button(page)

        if success:
            log("[OK] Refresh button clicked successfully!")
            page.wait_for_timeout(3000)  # let the refresh request fire
        else:
            log("[FAIL] Refresh button NOT found. Check debug_screenshot.png for the current page state.")
            context.close()
            sys.exit(2)

        context.close()
        log("Done. Browser closed.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="FiveCross TA Tag Refresher — click the tag refresh button automatically."
    )
    parser.add_argument(
        "--show",
        action="store_true",
        default=False,
        help="Show the browser window (useful for debugging).",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        default=False,
        help="Force a fresh login by clearing the saved session first.",
    )
    args = parser.parse_args()

    run(headless=not args.show, force_login=args.login)


if __name__ == "__main__":
    main()
