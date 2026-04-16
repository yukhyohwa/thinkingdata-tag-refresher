"""
Tag refresh actions — DOM interaction, JS helpers, dialog handling.
"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from refresher.config import log

# ---------------------------------------------------------------------------
# JavaScript snippets
# ---------------------------------------------------------------------------

# Read tag names from the name column in DOM order (used as fallback)
JS_GET_TAG_NAME_ORDER = """
() => {
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

# Build a {tagName: rowIndex} map by reading data-testid from refresh buttons
JS_BUILD_TESTID_MAP = """
() => {
    const result = {};
    const btns = Array.from(document.querySelectorAll(
        'button[data-testid^="tag-list-edit-map-refresh-btn-"]'
    ));
    btns.forEach(btn => {
        const testid = btn.getAttribute("data-testid");
        const rowIdx = parseInt(testid.replace("tag-list-edit-map-refresh-btn-", ""), 10);
        const row = btn.closest(".art-table-row");
        if (row) {
            const nameEl = row.querySelector('[class*="name___"] span, a[class*="name"] span');
            const name = nameEl ? (nameEl.innerText || nameEl.textContent || "").trim() : "";
            if (name) result[name] = rowIdx;
        }
    });
    return result;
}
"""

# Click the '更新' button in the confirmation modal
JS_CONFIRM_UPDATE_DIALOG = """
() => {
    const modalFooter = document.querySelector('.ant-modal-footer, .ant-modal-confirm-btns');
    if (!modalFooter) {
        return { success: false, error: 'No modal footer found' };
    }
    const primaryBtn = modalFooter.querySelector('.tant-next-button-primary, button.ant-btn-primary');
    if (primaryBtn && primaryBtn.offsetParent !== null) {
        const txt = (primaryBtn.innerText || primaryBtn.textContent || '').trim();
        primaryBtn.click();
        return { success: true, btnText: txt, method: 'tant-next-button-primary' };
    }
    const allBtns = Array.from(modalFooter.querySelectorAll('button')).filter(b => b.offsetParent !== null);
    for (const btn of allBtns) {
        const txt = (btn.innerText || btn.textContent || '').trim();
        if (txt === '更新' || txt.includes('更新')) {
            btn.click();
            return { success: true, btnText: txt, method: 'text-match-更新' };
        }
    }
    if (allBtns.length > 0) {
        const last = allBtns[allBtns.length - 1];
        last.click();
        return { success: true, btnText: (last.innerText || '').trim(), method: 'last-button-fallback' };
    }
    return { success: false, error: 'No button found in modal footer' };
}
"""

# Dismiss any lingering modal (cancel / close-X)
JS_DISMISS_OPEN_MODALS = """
() => {
    const modal = document.querySelector('.ant-modal, .ant-modal-wrap');
    if (!modal || modal.style.display === 'none') { return { found: false }; }
    const cancelBtns = Array.from(document.querySelectorAll(
        '.ant-modal-footer button, .ant-modal-confirm-btns button'
    )).filter(b => b.offsetParent !== null);
    for (const btn of cancelBtns) {
        const txt = (btn.innerText || btn.textContent || '').trim();
        if (txt === '取消' || txt.includes('取消') || txt === 'Cancel') {
            btn.click();
            return { found: true, dismissed: true, btnText: txt };
        }
    }
    const closeBtn = document.querySelector('.ant-modal-close, .ant-modal-confirm-close');
    if (closeBtn) {
        closeBtn.click();
        return { found: true, dismissed: true, method: 'close-x' };
    }
    return { found: true, dismissed: false };
}
"""


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def resolve_tag_indices(page: Page, tags: list[str]) -> dict[str, int]:
    """
    Return a {tag_name: row_index} map.
    Primary strategy: read data-testid attributes from the refresh buttons.
    Fallback: use DOM name order.
    """
    log("Resolving tag row indices via data-testid...")
    tag_indices: dict[str, int] = {}

    try:
        testid_map: dict = page.evaluate(JS_BUILD_TESTID_MAP)
        log(f"  data-testid map: {testid_map}")
        for tag in tags:
            if tag in testid_map:
                tag_indices[tag] = testid_map[tag]
                log(f"  {tag} -> row {tag_indices[tag]}")
            else:
                log(f"  {tag} -> NOT FOUND via data-testid")
    except Exception as e:
        log(f"  data-testid map error: {e}")

    # Fallback to name-order index
    if not tag_indices:
        log("  Falling back to DOM name order...")
        try:
            all_names: list = page.evaluate(JS_GET_TAG_NAME_ORDER)
            for tag in tags:
                if tag in all_names:
                    tag_indices[tag] = all_names.index(tag)
                    log(f"  {tag} -> index {tag_indices[tag]} (name order)")
                else:
                    idx = next((i for i, n in enumerate(all_names) if tag in n or n in tag), -1)
                    tag_indices[tag] = idx
                    log(f"  {tag} -> index {idx} (partial match)")
        except Exception as e:
            log(f"  Name order fallback error: {e}")

    return tag_indices


def dismiss_open_modal(page: Page) -> None:
    """Close any lingering modal before starting the next refresh."""
    try:
        modal = page.query_selector(".ant-modal, .ant-modal-wrap")
        if not modal or not modal.is_visible():
            return
        modal_text = modal.inner_text()
        if "更新" in modal_text or "标签" in modal_text:
            log("  [pre-check] Confirming lingering dialog...")
            page.evaluate(JS_CONFIRM_UPDATE_DIALOG)
            try:
                page.wait_for_selector(".ant-modal, .ant-modal-confirm", state="hidden", timeout=5000)
            except PlaywrightTimeout:
                pass
        else:
            result = page.evaluate(JS_DISMISS_OPEN_MODALS)
            if result.get("found"):
                log(f"  [pre-check] Closed lingering modal: {result}")
            page.wait_for_timeout(400)
    except Exception as e:
        log(f"  [pre-check] Error handling open modal: {e}")


def _confirm_dialog(page: Page, tag_name: str) -> bool:
    """Wait for the '更新标签数据' dialog and click '更新'. Returns True on success."""
    log(f"  Waiting for confirmation dialog (or immediate refresh)...")
    try:
        page.wait_for_selector(".ant-modal, .ant-modal-confirm, .ant-modal-body", timeout=10000)
        page.wait_for_timeout(500)
    except PlaywrightTimeout:
        log(f"  No dialog appeared for '{tag_name}' — refresh fired immediately. OK.")
        return True

    try:
        result = page.evaluate(JS_CONFIRM_UPDATE_DIALOG)
        log(f"  Confirm dialog result: {result}")
        if not (isinstance(result, dict) and result.get("success")):
            log(f"  WARNING: Could not click confirm button — pressing Enter as fallback.")
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
    except Exception as e:
        log(f"  Error clicking confirm button: {e}")
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)

    try:
        page.wait_for_selector(".ant-modal, .ant-modal-confirm", state="hidden", timeout=10000)
        log(f"  Dialog closed. Refresh confirmed for '{tag_name}'.")
    except PlaywrightTimeout:
        log(f"  WARNING: Dialog did not close within timeout for '{tag_name}' — proceeding anyway.")

    return True


def refresh_tag(page: Page, tag_name: str, row_index: int) -> bool:
    """
    Hover over the target row, click its refresh button (identified by
    data-testid), then confirm the dialog.
    """
    testid = f"tag-list-edit-map-refresh-btn-{row_index}"
    log(f"  Using data-testid: {testid}")

    # Hover to reveal action buttons
    try:
        rows = page.query_selector_all(".art-table-row")
        if row_index < len(rows):
            rows[row_index].hover()
            page.wait_for_timeout(800)
            log(f"  Hovered over row {row_index}")
        else:
            log(f"  WARNING: row_index {row_index} out of range ({len(rows)} rows)")
    except Exception as e:
        log(f"  Hover error: {e}")

    # Click the refresh button
    clicked = False
    try:
        btn = page.query_selector(f'button[data-testid="{testid}"]')
        if btn and btn.is_visible():
            btn.click()
            clicked = True
            log("  Clicked refresh button via data-testid.")
        else:
            log("  Button not visible, trying JS click...")
            result = page.evaluate(f'''() => {{
                const btn = document.querySelector('button[data-testid="{testid}"]');
                if (btn) {{ btn.click(); return true; }}
                return false;
            }}''')
            if result:
                clicked = True
                log("  JS click succeeded.")
            else:
                log(f"  Button '{testid}' not found in DOM.")
    except Exception as e:
        log(f"  Click error: {e}")

    if not clicked:
        return False

    return _confirm_dialog(page, tag_name)
