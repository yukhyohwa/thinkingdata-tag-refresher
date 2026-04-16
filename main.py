"""
FiveCross TA Tag Refresher
==========================
Entry point. Parses CLI args and runs the refresh workflow.

Usage:
    python main.py              # headless (for scheduled tasks)
    python main.py --show       # visible browser (for debugging)
    python main.py --login      # force re-login (clears saved session)
    python main.py --login --show
"""

import argparse
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from refresher.config import (
    TAG_URL, TAGS_TO_REFRESH, WAIT_AFTER_REFRESH_MS, log
)
from refresher.browser import (
    clear_session, launch_context, ensure_logged_in
)
from refresher.tag_actions import (
    resolve_tag_indices, dismiss_open_modal, refresh_tag
)


def run(headless: bool = True, force_login: bool = False) -> None:
    if force_login:
        clear_session()

    with sync_playwright() as p:
        context = launch_context(p, headless)
        page = context.new_page()

        # ── 1. Navigate ──────────────────────────────────────────────────
        log(f"Navigating to: {TAG_URL}")
        page.goto(TAG_URL)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass

        # ── 2. Login if needed ───────────────────────────────────────────
        ensure_logged_in(page)

        # ── 3. Wait for table ────────────────────────────────────────────
        log("Waiting for tag table to load...")
        try:
            page.wait_for_selector(
                ".art-table-row, .art-table, [class*='tableRow'], [class*='art-table']",
                timeout=25000,
            )
            log("Tag table loaded.")
        except PlaywrightTimeout:
            log("WARNING: Table not found within timeout; proceeding anyway.")
        page.wait_for_timeout(2000)

        # ── 4. Resolve row indices ───────────────────────────────────────
        tag_indices = resolve_tag_indices(page, TAGS_TO_REFRESH)

        log("-" * 50)
        log(f"Will refresh {len(TAGS_TO_REFRESH)} tags in order:")
        for i, name in enumerate(TAGS_TO_REFRESH, 1):
            log(f"  {i}. {name}")
        log("-" * 50)

        # ── 5. Refresh each tag ──────────────────────────────────────────
        results: dict[str, bool] = {}
        for i, tag_name in enumerate(TAGS_TO_REFRESH, 1):
            dismiss_open_modal(page)
            page.wait_for_timeout(400)

            log(f"[{i}/{len(TAGS_TO_REFRESH)}] Refreshing: {tag_name}")

            idx = tag_indices.get(tag_name, -1)
            if idx < 0:
                log(f"  [FAIL] '{tag_name}' not found in index map.")
                results[tag_name] = False
                log("-" * 50)
                continue

            ok = False
            for attempt in range(2):
                if attempt > 0:
                    log(f"  Attempt {attempt + 1}: Reloading page...")
                    page.goto(TAG_URL)
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                        page.wait_for_selector(".art-table-row", timeout=20000)
                        page.wait_for_timeout(1000)
                    except Exception:
                        pass

                ok = refresh_tag(page, tag_name, idx)
                if ok:
                    break
                log(f"  Refresh failed (attempt {attempt + 1}).")

            results[tag_name] = ok
            log(f"  -> {'OK' if ok else 'FAILED'}")

            if ok:
                page.wait_for_timeout(WAIT_AFTER_REFRESH_MS)
                try:
                    page.wait_for_selector(
                        '[class*="name___"] span, a[class*="name"] span', timeout=8000
                    )
                    page.wait_for_timeout(500)
                except Exception:
                    pass

            log("-" * 50)

        # ── 6. Summary ───────────────────────────────────────────────────
        log("=== Refresh Summary ===")
        failed = [name for name, ok in results.items() if not ok]
        for tag_name, ok in results.items():
            log(f"  {'[OK]  ' if ok else '[FAIL]'} {tag_name}")

        context.close()

        if failed:
            log(f"WARNING: {len(failed)} tag(s) failed: {', '.join(failed)}")
            log("TIP: Run with --show to debug visually.")
            sys.exit(2)
        else:
            log("All tags refreshed successfully!")
            log("Done. Browser closed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FiveCross TA Tag Refresher"
    )
    parser.add_argument("--show",  action="store_true", help="Show browser window.")
    parser.add_argument("--login", action="store_true", help="Force re-login.")
    args = parser.parse_args()
    run(headless=not args.show, force_login=args.login)


if __name__ == "__main__":
    main()
