"""
fivecross-ta-tag-refresher
==========================
Navigates to the ThinkingData tag management page, auto-logs in if needed
(using a persistent browser session so subsequent runs stay logged in),
then sequentially clicks the refresh button for each configured tag name.

Tags refreshed (in order):
  fixed_regdate -> fixed_affcode -> fixed_os -> fixed_country -> fixed_freeamount

NOTE: The page uses ali-react-table which splits tag names and operation buttons
into separate DOM sections. We use JavaScript to find the row index by tag name
from the left-sticky section, then click the corresponding button in the right
operations section.

Usage:
    python refresh_tag.py          # headless (for scheduled tasks / bat)
    python refresh_tag.py --show   # visible browser (for debugging)
    python refresh_tag.py --login  # force re-login (clears old session first)
"""

import os
import sys
import time
import shutil
import argparse
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

TA_URL      = os.getenv("TA_URL",  "http://8.211.141.76:8993/")
TA_USER     = os.getenv("TA_USER", "")
TA_PASS     = os.getenv("TA_PASS", "")
TAG_URL     = os.getenv("TAG_URL", "http://8.211.141.76:8993/#/tag/tag/1?currentProjectId=16")
SESSION_DIR = os.path.abspath(os.getenv("SESSION_DIR", "./ta_session"))

# Tags to refresh, in order
TAGS_TO_REFRESH = [
    "fixed_regdate",
    "fixed_affcode",
    "fixed_os",
    "fixed_country",
    "fixed_freeamount",
]

# How long (ms) to wait after clicking refresh before moving to next tag
WAIT_AFTER_REFRESH_MS = int(os.getenv("WAIT_AFTER_REFRESH", "5")) * 1000

os.makedirs(SESSION_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    safe_msg = msg.encode("gbk", errors="replace").decode("gbk")
    print(f"[{ts}] {safe_msg}", flush=True)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def clear_session():
    if os.path.exists(SESSION_DIR):
        shutil.rmtree(SESSION_DIR, ignore_errors=True)
    os.makedirs(SESSION_DIR, exist_ok=True)
    log("Session cleared. Will perform fresh login.")


def is_login_page(page) -> bool:
    return (
        "login" in page.url.lower()
        or bool(page.query_selector('input[type="password"]'))
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def perform_login(page):
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

    # Try to tick "remember me / 7天免登录"
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


# ---------------------------------------------------------------------------
# JS-based tag refresh (handles ali-react-table split DOM)
# ---------------------------------------------------------------------------

# JavaScript that:
# 1. Finds all art-table-row elements
# 2. Searches for the row whose text content matches the tag name
# 3. Gets the row index from the left (name) section
# 4. Finds the corresponding row in the rightmost (operations) section
# 5. Clicks the first button (refresh icon)
JS_REFRESH_TAG = """
(tagName) => {
    // Find all table bodies (ali-react-table renders multiple)
    const bodies = Array.from(document.querySelectorAll(
        '.art-table-body, .art-virtual-scroll-container, .art-table-content'
    ));

    // Also try to find by tbody sections inside the wrapper
    const allRowGroups = Array.from(document.querySelectorAll(
        '.art-table-body > div, .art-sticky-left .art-table-row, ' +
        '[class*="art-table"] .art-table-row'
    ));

    // Strategy A: Find by row index approach
    // First locate all rows that have tag names in the LEFT (sticky) column
    const nameRows = Array.from(document.querySelectorAll('.art-table-row, [class*="tableRow"]'));

    // Find the row index whose text contains our tag name
    let targetIndex = -1;
    for (let i = 0; i < nameRows.length; i++) {
        const rowText = nameRows[i].innerText || nameRows[i].textContent || '';
        if (rowText.includes(tagName)) {
            targetIndex = i;
            break;
        }
    }

    if (targetIndex === -1) {
        // Strategy B: Search ALL text on page for the tag name in any element
        // The name column is the sticky-left section
        const allCells = Array.from(document.querySelectorAll('td, .art-td, [class*="tableCell"]'));
        for (let i = 0; i < allCells.length; i++) {
            const txt = allCells[i].innerText || allCells[i].textContent || '';
            if (txt.trim() === tagName || txt.includes(tagName)) {
                // Go up to find the row
                let row = allCells[i].closest('.art-table-row, tr, [class*="tableRow"]');
                if (row) {
                    const parent = row.parentElement;
                    if (parent) {
                        targetIndex = Array.from(parent.children).indexOf(row);
                    }
                    break;
                }
            }
        }
    }

    // Strategy C: Find via anchor/link with class "name___"
    if (targetIndex === -1) {
        const links = Array.from(document.querySelectorAll('[class*="name___"] span, a[class*="name"] span'));
        for (let i = 0; i < links.length; i++) {
            if ((links[i].innerText || links[i].textContent || '').trim() === tagName) {
                let row = links[i].closest('.art-table-row, tr');
                if (row) {
                    const parent = row.parentElement;
                    targetIndex = parent ? Array.from(parent.children).indexOf(row) : i;
                    break;
                }
                targetIndex = i;
                break;
            }
        }
    }

    if (targetIndex === -1) {
        return { success: false, error: 'Tag name row not found: ' + tagName };
    }

    // Now find the refresh button in the corresponding row
    // In ali-react-table, the operations column is in a separate DOM.
    // We click the button at the same row index.

    // Method 1: All buttons with title="刷新" (most precise)
    const refreshBtns = Array.from(document.querySelectorAll(
        'button[title="刷新"], button.tant-next-button-only-icon, ' +
        '.ant-btn-sm.tant-next-button-only-icon'
    ));
    if (refreshBtns.length > 0) {
        // Each tag row has one refresh button; targetIndex maps directly
        const btn = refreshBtns[targetIndex] || refreshBtns[0];
        if (btn) {
            btn.click();
            return { success: true, method: 'title=刷新, index=' + targetIndex, found: refreshBtns.length };
        }
    }

    // Method 2: Find all art-table-row in the non-sticky (operations) section
    // and click button[0] in the row at targetIndex
    const opSections = Array.from(document.querySelectorAll(
        '.art-right [class*="row"], .art-table-body [class*="row"], ' +
        '.art-sticky-right .art-table-row'
    ));
    if (opSections.length > targetIndex) {
        const opRow = opSections[targetIndex];
        const btn = opRow.querySelector('button');
        if (btn) {
            btn.click();
            return { success: true, method: 'opSection row[' + targetIndex + ']' };
        }
    }

    // Method 3: All .ant-btn-sm buttons globally (fallback)
    const allSmBtns = Array.from(document.querySelectorAll('.ant-btn-sm')).filter(
        b => b.offsetParent !== null  // visible only
    );
    // Each tag row likely has multiple buttons; group by row
    // Just pick the first button at chunk = targetIndex * buttonsPerRow
    if (allSmBtns.length > 0) {
        const buttonsPerRow = Math.ceil(allSmBtns.length / nameRows.length) || 1;
        const idx = targetIndex * buttonsPerRow;
        const btn = allSmBtns[idx];
        if (btn) {
            btn.click();
            return { success: true, method: 'ant-btn-sm[' + idx + '] (est. ' + buttonsPerRow + '/row)' };
        }
    }

    return { success: false, error: 'Could not locate refresh button at index ' + targetIndex };
}
"""

# Simpler direct JS for when we just need all refresh buttons in DOM order
JS_GET_ALL_REFRESH_BTNS = """
() => {
    const btns = Array.from(document.querySelectorAll(
        'button[title="刷新"], button.tant-next-button-only-icon'
    )).filter(b => b.offsetParent !== null);
    return btns.length;
}
"""

JS_CLICK_NTH_REFRESH_BTN = """
(n) => {
    const btns = Array.from(document.querySelectorAll(
        'button[title="刷新"], button.tant-next-button-only-icon'
    )).filter(b => b.offsetParent !== null);
    if (btns[n]) {
        btns[n].click();
        return { success: true, total: btns.length, clicked: n };
    }
    return { success: false, total: btns.length, requested: n };
}
"""

JS_CONFIRM_UPDATE_DIALOG = """
() => {
    // The confirm modal has buttons in .ant-modal-footer:
    //   Cancel: class 'tant-next-button-text'          (NOT primary)
    //   Update: class 'tant-next-button-primary'       (the one we want)
    const modalFooter = document.querySelector('.ant-modal-footer, .ant-modal-confirm-btns');
    if (!modalFooter) {
        return { success: false, error: 'No modal footer found' };
    }

    // Priority 1: .tant-next-button-primary (the Update button)
    const primaryBtn = modalFooter.querySelector(
        '.tant-next-button-primary, button.ant-btn-primary'
    );
    if (primaryBtn && primaryBtn.offsetParent !== null) {
        const txt = (primaryBtn.innerText || primaryBtn.textContent || '').trim();
        primaryBtn.click();
        return { success: true, btnText: txt, method: 'tant-next-button-primary' };
    }

    // Priority 2: Button whose text is exactly '更新'
    const allBtns = Array.from(modalFooter.querySelectorAll('button')).filter(
        b => b.offsetParent !== null
    );
    for (const btn of allBtns) {
        const txt = (btn.innerText || btn.textContent || '').trim();
        if (txt === '更新' || txt.includes('更新')) {
            btn.click();
            return { success: true, btnText: txt, method: 'text-match-更新' };
        }
    }

    // Priority 3: Last button in footer (usually confirm)
    if (allBtns.length > 0) {
        const last = allBtns[allBtns.length - 1];
        last.click();
        return { success: true, btnText: (last.innerText || '').trim(), method: 'last-button-fallback' };
    }

    return { success: false, error: 'No button found in modal footer', html: modalFooter.innerHTML.substring(0, 300) };
}
"""

JS_DISMISS_OPEN_MODALS = """
() => {
    // If there is any lingering open modal, click its Cancel/Close button
    const modal = document.querySelector('.ant-modal, .ant-modal-wrap');
    if (!modal || modal.style.display === 'none') {
        return { found: false };
    }
    // Try clicking the 取消 (cancel) button
    const cancelBtns = Array.from(document.querySelectorAll('.ant-modal-footer button, .ant-modal-confirm-btns button'))
        .filter(b => b.offsetParent !== null);
    for (const btn of cancelBtns) {
        const txt = (btn.innerText || btn.textContent || '').trim();
        if (txt === '取消' || txt.includes('取消') || txt === 'Cancel') {
            btn.click();
            return { found: true, dismissed: true, btnText: txt };
        }
    }
    // Click the X close button
    const closeBtn = document.querySelector('.ant-modal-close, .ant-modal-confirm-close');
    if (closeBtn) {
        closeBtn.click();
        return { found: true, dismissed: true, method: 'close-x' };
    }
    return { found: true, dismissed: false };
}
"""

JS_GET_TAG_NAME_ORDER = """
() => {
    // Read tag names in DOM order from the name column
    const nameEls = Array.from(document.querySelectorAll(
        '[class*="name___"] span, a[class*="name"] span, ' +
        '.art-table-row [class*="name"] span, .art-table-row td:first-child span'
    )).filter(el => {
        const txt = (el.innerText || el.textContent || '').trim();
        return txt.length > 0 && !txt.includes('\\n');
    });
    return nameEls.map(el => (el.innerText || el.textContent || '').trim());
}
"""


def _dismiss_open_modal(page):
    """
    If a refresh confirmation modal ('更新标签数据') is currently open,
    confirm it by clicking '更新' (so the previous tag's refresh is properly committed).
    This prevents a lingering dialog from blocking the next tag's operations.
    """
    try:
        modal = page.query_selector(".ant-modal, .ant-modal-wrap")
        if not modal or not modal.is_visible():
            return

        # Check if it's a refresh confirmation dialog
        modal_text = modal.inner_text()
        if "更新" in modal_text or "标签" in modal_text:
            log("  [pre-check] Confirming lingering '更新标签数据' dialog...")
            result = page.evaluate(JS_CONFIRM_UPDATE_DIALOG)
            log(f"  [pre-check] Auto-confirm result: {result}")
            # Wait for dialog to close
            try:
                page.wait_for_selector(".ant-modal, .ant-modal-confirm", state="hidden", timeout=5000)
            except PlaywrightTimeout:
                pass
        else:
            # Close/cancel other types of modals
            result = page.evaluate(JS_DISMISS_OPEN_MODALS)
            if result.get("found"):
                log(f"  [pre-check] Closed lingering modal: {result}")
            page.wait_for_timeout(400)
    except Exception as e:
        log(f"  [pre-check] Error handling open modal: {e}")


def refresh_tag_by_js(page, tag_name: str) -> bool:
    """
    1. Find the tag's row index from the DOM name list.
    2. Click the N-th refresh button (circular arrow icon).
    3. Wait for the confirmation dialog '更新标签数据' to appear.
    4. Click the '更新' (Update) button to confirm.
    5. Wait for the dialog to close before returning.
    """
    # Step 1: Read tag name order from DOM
    try:
        names = page.evaluate(JS_GET_TAG_NAME_ORDER)
        log(f"  Found {len(names)} tag names in DOM.")

        if tag_name in names:
            idx = names.index(tag_name)
            log(f"  Tag '{tag_name}' is at index {idx}")
        else:
            # Try partial match
            idx = next((i for i, n in enumerate(names) if tag_name in n or n in tag_name), -1)
            if idx >= 0:
                log(f"  Partial match: '{names[idx]}' at index {idx}")
            else:
                log(f"  Tag '{tag_name}' NOT found in name list. Trying JS strategy...")
                result = page.evaluate(JS_REFRESH_TAG, tag_name)
                log(f"  JS result: {result}")
                if not (isinstance(result, dict) and result.get("success")):
                    return False
                # Still need to confirm the dialog
                return _confirm_dialog(page, tag_name)
    except Exception as e:
        log(f"  Error reading tag names: {e}")
        idx = -1

    # Step 2: How many refresh buttons are visible?
    try:
        total_btns = page.evaluate(JS_GET_ALL_REFRESH_BTNS)
        log(f"  Total visible refresh buttons: {total_btns}")
    except Exception as e:
        log(f"  Error counting buttons: {e}")
        total_btns = 0

    # Step 3: Click the N-th refresh button
    clicked = False
    if idx >= 0 and total_btns > 0:
        try:
            result = page.evaluate(JS_CLICK_NTH_REFRESH_BTN, idx)
            log(f"  Click result: {result}")
            if isinstance(result, dict) and result.get("success"):
                clicked = True
        except Exception as e:
            log(f"  Error clicking button[{idx}]: {e}")

    if not clicked:
        # Fallback: use the more complex JS
        try:
            result = page.evaluate(JS_REFRESH_TAG, tag_name)
            log(f"  Fallback JS result: {result}")
            if isinstance(result, dict) and result.get("success"):
                clicked = True
        except Exception as e:
            log(f"  Fallback JS error: {e}")

    if not clicked:
        return False

    # Step 4 & 5: Handle confirmation dialog
    return _confirm_dialog(page, tag_name)


def _confirm_dialog(page, tag_name: str) -> bool:
    """
    Wait for the confirmation modal to appear, then click '更新'.
    If NO dialog appears within the timeout, that is OK — it means the tag
    refreshes immediately without confirmation (some tags behave this way).
    Returns True in both cases (dialog confirmed OR no dialog needed).
    """
    log(f"  Waiting for confirmation dialog (or immediate refresh)...")
    try:
        page.wait_for_selector(
            ".ant-modal, .ant-modal-confirm, .ant-modal-body",
            timeout=10000,
        )
        page.wait_for_timeout(500)  # let the animation settle
    except PlaywrightTimeout:
        # No dialog appeared — the refresh fired immediately. That's fine.
        log(f"  No dialog appeared for '{tag_name}' — refresh fired immediately. OK.")
        return True

    # Dialog appeared — click the '更新' (Update/Confirm) button
    try:
        confirm_result = page.evaluate(JS_CONFIRM_UPDATE_DIALOG)
        log(f"  Confirm dialog result: {confirm_result}")
        if not (isinstance(confirm_result, dict) and confirm_result.get("success")):
            log(f"  WARNING: Could not click confirm button for '{tag_name}'")
            # Try pressing Enter as fallback
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
    except Exception as e:
        log(f"  Error clicking confirm button: {e}")
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)

    # Wait for dialog to close
    try:
        page.wait_for_selector(
            ".ant-modal, .ant-modal-confirm",
            state="hidden",
            timeout=10000,
        )
        log(f"  Dialog closed. Refresh confirmed for '{tag_name}'.")
    except PlaywrightTimeout:
        log(f"  WARNING: Dialog did not close within timeout for '{tag_name}' — proceeding anyway.")

    return True



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
            slow_mo=60,
            permissions=["clipboard-read", "clipboard-write"],
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()

        # ----------------------------------------------------------------
        # Step 1: Navigate to tag page
        # ----------------------------------------------------------------
        log(f"Navigating to: {TAG_URL}")
        page.goto(TAG_URL)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass

        # ----------------------------------------------------------------
        # Step 2: Login if required
        # ----------------------------------------------------------------
        if is_login_page(page):
            if not TA_USER or not TA_PASS:
                log("ERROR: Credentials not set. Edit .env and re-run.")
                context.close()
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

        # ----------------------------------------------------------------
        # Step 3: Wait for table to load
        # ----------------------------------------------------------------
        log("Waiting for tag table to load...")
        try:
            page.wait_for_selector(
                ".art-table-row, .art-table, [class*='tableRow'], [class*='art-table']",
                timeout=25000,
            )
            log("Tag table loaded.")
        except PlaywrightTimeout:
            log("WARNING: Table not found within timeout; proceeding anyway.")

        # Extra time for full SPA render
        page.wait_for_timeout(2000)

        # ----------------------------------------------------------------
        # Step 4: Pre-resolve all tag indices (do this ONCE while all rows
        # are visible, before any refresh triggers DOM changes)
        # Wait with retry in case the SPA hasn't fully rendered yet
        # ----------------------------------------------------------------
        log("Pre-resolving tag row indices...")
        all_names = []
        for attempt in range(5):
            try:
                candidate_names = page.evaluate(JS_GET_TAG_NAME_ORDER)
                if candidate_names:
                    all_names = candidate_names
                    break
                else:
                    log(f"  Attempt {attempt+1}: DOM names empty, retrying in 2s...")
                    page.wait_for_timeout(2000)
            except Exception as e:
                log(f"  Attempt {attempt+1}: Error reading tag names: {e}, retrying in 2s...")
                page.wait_for_timeout(2000)

        log(f"  All tag names in DOM ({len(all_names)}): {all_names}")

        # Build index map
        tag_indices = {}
        for tag_name in TAGS_TO_REFRESH:
            if tag_name in all_names:
                tag_indices[tag_name] = all_names.index(tag_name)
                log(f"  {tag_name} -> index {tag_indices[tag_name]}")
            else:
                # partial match
                idx = next((i for i, n in enumerate(all_names) if tag_name in n or n in tag_name), -1)
                tag_indices[tag_name] = idx
                if idx >= 0:
                    log(f"  {tag_name} -> index {idx} (partial match: '{all_names[idx]}')")
                else:
                    log(f"  {tag_name} -> NOT FOUND in DOM name list")

        # Total refresh buttons baseline
        try:
            total_btns_baseline = page.evaluate(JS_GET_ALL_REFRESH_BTNS)
            log(f"  Total visible refresh buttons: {total_btns_baseline}")
        except Exception:
            total_btns_baseline = 0

        log("-" * 50)

        # ----------------------------------------------------------------
        # Step 5: Sequentially refresh each tag
        # ----------------------------------------------------------------
        log(f"Will refresh {len(TAGS_TO_REFRESH)} tags in order:")
        for i, name in enumerate(TAGS_TO_REFRESH, 1):
            log(f"  {i}. {name}")
        log("-" * 50)

        results = {}
        for i, tag_name in enumerate(TAGS_TO_REFRESH, 1):
            # Dismiss any lingering modal from the previous operation
            _dismiss_open_modal(page)
            page.wait_for_timeout(400)

            log(f"[{i}/{len(TAGS_TO_REFRESH)}] Refreshing: {tag_name}")

            # Use the pre-resolved index
            idx = tag_indices.get(tag_name, -1)
            if idx < 0:
                log(f"  [FAIL] Tag '{tag_name}' not found in pre-resolved index map.")
                results[tag_name] = False
                log("-" * 50)
                continue

            # --- Retry loop with Page Reload fallback ---
            ok = False
            for attempt in range(2):
                if attempt > 0:
                    log(f"  Attempt {attempt+1}: Reloading page to fix table state...")
                    page.goto(TAG_URL)
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                        page.wait_for_selector(".art-table-row, [class*='tableRow']", timeout=20000)
                        page.wait_for_timeout(1000)
                    except Exception:
                        pass

                # Pre-scroll
                try:
                    page.evaluate("""
                        (rowIndex) => {
                            const containers = [
                                document.querySelector('.art-virtual-scroll-container'),
                                document.querySelector('.art-table-body'),
                                document.querySelector('.ant-table-body'),
                            ].filter(Boolean);
                            for (const c of containers) {
                                c.scrollTop = rowIndex * 48;
                            }
                            const nameEls = Array.from(document.querySelectorAll('[class*="name___"] span, a[class*="name"] span'));
                            if (nameEls[rowIndex]) nameEls[rowIndex].scrollIntoView({ block: 'center' });
                        }
                    """, idx)
                    page.wait_for_timeout(800)
                except Exception: pass

                # Hover reveal
                clicked = False
                try:
                    name_els = page.query_selector_all('[class*="name___"] span, a[class*="name"] span')
                    target_el = None
                    for el in name_els:
                        try:
                            if el.inner_text().strip() == tag_name:
                                target_el = el; break
                        except Exception: pass

                    if target_el:
                        target_el.hover()
                        page.wait_for_timeout(600)
                        
                        total_btns = page.evaluate(JS_GET_ALL_REFRESH_BTNS)
                        if total_btns > idx:
                            result = page.evaluate(JS_CLICK_NTH_REFRESH_BTN, idx)
                            if result.get("success"): clicked = True
                    
                    if not clicked:
                        # Fallback: Just try to click by index anyway if buttons are visible
                        total_btns = page.evaluate(JS_GET_ALL_REFRESH_BTNS)
                        if total_btns > idx:
                            result = page.evaluate(JS_CLICK_NTH_REFRESH_BTN, idx)
                            if result.get("success"): clicked = True

                except Exception as e:
                    log(f"  Click error: {e}")

                if clicked:
                    ok = _confirm_dialog(page, tag_name)
                    if ok: break # success!
                else:
                    log(f"  Tag '{tag_name}' row/button not found (Attempt {attempt+1}).")
            
            # --- End of Retry loop ---

            results[tag_name] = ok
            log(f"  -> {'OK' if ok else 'FAILED'}")

            if ok:
                page.wait_for_timeout(WAIT_AFTER_REFRESH_MS)
                # Wait for recovery
                try:
                    page.wait_for_selector('[class*="name___"] span, a[class*="name"] span', timeout=8000)
                    page.wait_for_timeout(500)
                except Exception: pass

            log("-" * 50)


        # ----------------------------------------------------------------
        # Step 5: Summary
        # ----------------------------------------------------------------
        log("=== Refresh Summary ===")
        failed = []
        for tag_name, ok in results.items():
            status = "[OK]  " if ok else "[FAIL]"
            log(f"  {status} {tag_name}")
            if not ok:
                failed.append(tag_name)

        context.close()

        if failed:
            log(f"WARNING: {len(failed)} tag(s) failed: {', '.join(failed)}")
            log("TIP: Run with --show to debug visually.")
            sys.exit(2)
        else:
            log("All tags refreshed successfully!")
            log("Done. Browser closed.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="FiveCross TA Tag Refresher - sequentially refresh configured tags."
    )
    parser.add_argument(
        "--show", action="store_true", default=False,
        help="Show the browser window (useful for debugging).",
    )
    parser.add_argument(
        "--login", action="store_true", default=False,
        help="Force a fresh login by clearing the saved session first.",
    )
    args = parser.parse_args()
    run(headless=not args.show, force_login=args.login)


if __name__ == "__main__":
    main()
