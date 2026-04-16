"""
Browser lifecycle — launch, session management, login.
"""

import os
import shutil
import sys

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout

from refresher.config import SESSION_DIR, TA_USER, TA_PASS, TAG_URL, log


def clear_session() -> None:
    """Delete the saved browser session so the next run performs a fresh login."""
    if os.path.exists(SESSION_DIR):
        shutil.rmtree(SESSION_DIR, ignore_errors=True)
    os.makedirs(SESSION_DIR, exist_ok=True)
    log("Session cleared. Will perform fresh login.")


def launch_context(playwright, headless: bool) -> BrowserContext:
    """Launch a persistent Chromium context backed by SESSION_DIR."""
    log(f"Launching browser (headless={headless}) ...")
    log(f"Session dir: {SESSION_DIR}")
    return playwright.chromium.launch_persistent_context(
        SESSION_DIR,
        headless=headless,
        slow_mo=60,
        permissions=["clipboard-read", "clipboard-write"],
        viewport={"width": 1440, "height": 900},
    )


def is_login_page(page: Page) -> bool:
    return (
        "login" in page.url.lower()
        or bool(page.query_selector('input[type="password"]'))
    )


def perform_login(page: Page) -> None:
    """Fill credentials and submit the login form."""
    log("Login page detected - performing auto-login...")

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

    # Tick "remember me / 7天免登录" if present
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

    pass_input.focus()
    page.keyboard.press("Enter")

    try:
        page.wait_for_url(lambda url: "login" not in url.lower(), timeout=15000)
        log("Login successful!")
    except PlaywrightTimeout:
        page.wait_for_timeout(5000)
        if is_login_page(page):
            raise RuntimeError("Login failed - still on login page.")
        log("Login successful (URL unchanged but login page gone).")


def ensure_logged_in(page: Page) -> None:
    """Navigate to TAG_URL, login if needed, then navigate back."""
    if is_login_page(page):
        if not TA_USER or not TA_PASS:
            log("ERROR: Credentials not set. Edit .env and re-run.")
            sys.exit(1)
        perform_login(page)
        log(f"Navigating back to tag page: {TAG_URL}")
        page.goto(TAG_URL)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass
    else:
        log("Existing session detected - skipping login.")
