"""
Steam Wishlist Copier - Playwright Version (2025)
Automatically copy a Steam wishlist from one account to another.
"""
import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Constants
DEFAULT_RATE_LIMIT_DELAY = 4  # seconds between add actions (Steam rate limit: ~4 seconds per request in 2025)
DEFAULT_DOWNLOAD_DELAY = 0.3  # seconds between wishlist page downloads
DEFAULT_TIMEOUT_MS = 10000  # milliseconds for Playwright waits
TEMP_DIR = Path("temp_wishlist")
DEFAULT_STORAGE_STATE = Path("steam_storage.json")
ERROR_LOG = Path("wishlist_errors.json")


@dataclass
class DownloadConfig:
    user_id: str
    download_delay: float
    download_workers: int
    limit: Optional[int]


@dataclass
class AddConfig:
    rate_limit_delay: float
    headless: bool
    storage_state: Path
    save_storage: bool


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )
    return session


def download_wishlist_page(session: requests.Session, user_id: str, page: int) -> Dict:
    url = f"https://store.steampowered.com/wishlist/id/{user_id}/wishlistdata/?p={page}"
    response = session.get(url, timeout=30)
    if response.status_code == 403:
        raise ValueError("Wishlist is private or access is blocked (403)")
    response.raise_for_status()
    if "application/json" not in response.headers.get("Content-Type", ""):
        raise ValueError("Unexpected response. Wishlist might be private or blocked.")
    return response.json()


def download_wishlist(config: DownloadConfig) -> List[str]:
    """Download all wishlist pages from a Steam user."""
    print(f"Downloading wishlist for user: {config.user_id}")
    TEMP_DIR.mkdir(exist_ok=True)

    wishlist_data: Dict[str, dict] = {}
    session = build_session()

    page = 0
    empty_pages = 0
    max_workers = max(1, min(config.download_workers, 6))

    while True:
        print(f"Downloading page {page}...")
        try:
            if max_workers > 1:
                futures = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    for i in range(page, page + max_workers):
                        futures.append(executor.submit(download_wishlist_page, session, config.user_id, i))
                    for offset, future in enumerate(as_completed(futures)):
                        json_data = future.result()
                        if not json_data:
                            empty_pages += 1
                            continue
                        file_path = TEMP_DIR / f"wishlist{page + offset}.json"
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(json_data, f, ensure_ascii=False, indent=2)
                        wishlist_data.update(json_data)
                page += max_workers
            else:
                json_data = download_wishlist_page(session, config.user_id, page)
                if not json_data:
                    empty_pages += 1
                else:
                    file_path = TEMP_DIR / f"wishlist{page}.json"
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2)
                    wishlist_data.update(json_data)
                page += 1

            if config.limit and len(wishlist_data) >= config.limit:
                break

            if empty_pages >= 2:
                break

            time.sleep(config.download_delay)

        except ValueError as e:
            print(f"Wishlist unavailable: {e}")
            break
        except requests.RequestException as e:
            print(f"Error downloading page {page}: {e}")
            break

    app_ids = list(wishlist_data.keys())
    if config.limit:
        app_ids = app_ids[: config.limit]

    print(f"Downloaded {len(app_ids)} games")
    return app_ids


def cleanup_temp_files(keep: bool):
    """Remove temporary wishlist JSON files."""
    if keep:
        return
    if TEMP_DIR.exists():
        for file in TEMP_DIR.glob("wishlist*.json"):
            file.unlink()
        TEMP_DIR.rmdir()
        print("Temporary files cleaned up")


def login_to_steam(page, username: str, password: str, timeout_ms: int):
    """Log in to Steam account."""
    print("Navigating to Steam login page...")
    page.goto("https://store.steampowered.com/login/", wait_until="domcontentloaded")

    try:
        page.wait_for_selector("input[type='text']", timeout=timeout_ms)
        username_field = page.locator("input[type='text']").first
        password_field = page.locator("input[type='password']").first
        username_field.fill(username)
        password_field.fill(password)
        login_button = page.locator("button[type='submit']").first
        login_button.click()
        print("Login form submitted. Please complete any 2FA if required.")
    except PlaywrightTimeout as e:
        print(f"Error during login: {e}")
        raise


def handle_age_gate(page) -> bool:
    """Handle age verification if present."""
    try:
        age_gate = page.locator("#app_agegate")
        if age_gate.is_visible(timeout=2000):
            page.select_option("#ageDay", "13")
            page.select_option("#ageMonth", "April")
            page.select_option("#ageYear", "1993")
            page.locator("#view_product_page_btn").click()
            page.wait_for_load_state("domcontentloaded")
            return True
    except PlaywrightTimeout:
        return False
    except Exception:
        return False
    return False


def is_in_wishlist(page) -> bool:
    success = page.locator("#add_to_wishlist_area_success")
    if success.count() and success.is_visible(timeout=2000):
        return True
    wishlist_area = page.locator("#add_to_wishlist_area")
    if wishlist_area.count() == 0:
        return False
    style = wishlist_area.get_attribute("style")
    if style and "display: none" in style:
        return True
    return False


def add_to_wishlist(page, app_ids: List[str], rate_limit_delay: float) -> Tuple[int, int, int, List[str]]:
    """Add games to wishlist with proper rate limiting."""
    total = len(app_ids)
    added = 0
    skipped = 0
    errors = 0
    failed_ids: List[str] = []

    for idx, app_id in enumerate(app_ids, 1):
        print(f"[{idx}/{total}] Processing app ID: {app_id}")

        try:
            page.goto(f"https://store.steampowered.com/app/{app_id}", wait_until="domcontentloaded")
            page.wait_for_timeout(800)

            handle_age_gate(page)

            try:
                wishlist_area = page.locator("#add_to_wishlist_area")
                wishlist_area.wait_for(timeout=5000)

                if is_in_wishlist(page):
                    print("  → Already in wishlist, skipping")
                    skipped += 1
                else:
                    wishlist_area.click()
                    added += 1
                    print("  → Added to wishlist")
                    # jitter to look less bot-like
                    jitter = random.uniform(0.2, 0.8)
                    page.wait_for_timeout((rate_limit_delay + jitter) * 1000)

            except PlaywrightTimeout:
                print("  → Wishlist button not found, skipping")
                errors += 1
                failed_ids.append(app_id)

        except Exception as e:
            print(f"  → Error: {e}")
            errors += 1
            failed_ids.append(app_id)
            page.wait_for_timeout(2000)

    return added, skipped, errors, failed_ids


def show_wishlist_preview(app_ids: List[str], rate_limit_delay: float):
    """Show preview of games that would be added."""
    print("\n" + "=" * 60)
    print("WISHLIST PREVIEW")
    print("=" * 60)
    print(f"Total games to be added: {len(app_ids)}")
    print("\nFirst 10 game IDs:")
    for idx, app_id in enumerate(app_ids[:10], 1):
        print(f"  {idx}. App ID: {app_id}")
        print(f"     URL: https://store.steampowered.com/app/{app_id}")

    if len(app_ids) > 10:
        print(f"\n  ... and {len(app_ids) - 10} more games")

    print("\n" + "=" * 60)
    print(f"Estimated time: ~{len(app_ids) * rate_limit_delay / 60:.1f} minutes")
    print("=" * 60)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Steam Wishlist Copier - Automatically copy wishlists between Steam accounts"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download and preview wishlist without logging in or adding games",
    )
    parser.add_argument("--user", type=str, help="Source Steam user ID to copy wishlist from")
    parser.add_argument("--limit", type=int, help="Limit number of games to add (useful for testing)")
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=DEFAULT_RATE_LIMIT_DELAY,
        help="Seconds to wait between wishlist additions (default: 4)",
    )
    parser.add_argument(
        "--download-delay",
        type=float,
        default=DEFAULT_DOWNLOAD_DELAY,
        help="Delay between wishlist page downloads (default: 0.3)",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=2,
        help="Parallel download workers (default: 2)",
    )
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument(
        "--storage-state",
        type=str,
        default=str(DEFAULT_STORAGE_STATE),
        help="Path to Playwright storage state file",
    )
    parser.add_argument(
        "--save-storage",
        action="store_true",
        help="Save storage state after successful login",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep downloaded wishlist JSON files",
    )
    parser.add_argument(
        "--errors-file",
        type=str,
        default=str(ERROR_LOG),
        help="Path to save failed app IDs (JSON)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Steam Wishlist Copier - Playwright Edition (2025)")
    print("=" * 60)

    source_user = args.user or input("Input user ID that you want to copy from: ").strip()

    download_cfg = DownloadConfig(
        user_id=source_user,
        download_delay=args.download_delay,
        download_workers=args.download_workers,
        limit=args.limit,
    )

    app_ids = download_wishlist(download_cfg)

    if not app_ids:
        print("No games found in wishlist. Exiting.")
        cleanup_temp_files(args.no_cleanup)
        return

    if args.limit:
        print(f"\nLimiting to first {args.limit} games (--limit flag)")

    if args.dry_run:
        print("\n🧪 DRY-RUN MODE - No games will be added")
        show_wishlist_preview(app_ids, args.rate_limit)
        print("\nTo actually add these games, run without --dry-run flag")
        cleanup_temp_files(args.no_cleanup)
        return

    show_wishlist_preview(app_ids, args.rate_limit)

    print("\n" + "=" * 60)
    username = input("Input your Steam username: ").strip()
    password = input("Input your Steam password: ").strip()

    storage_state_path = Path(args.storage_state)

    with sync_playwright() as p:
        try:
            print("\nLaunching browser...")
            browser = p.chromium.launch(headless=args.headless)
            context_kwargs = {
                "viewport": {"width": 1280, "height": 720},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            if storage_state_path.exists():
                context_kwargs["storage_state"] = str(storage_state_path)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()

            if not storage_state_path.exists():
                login_to_steam(page, username, password, DEFAULT_TIMEOUT_MS)
                input("\nPress Enter after completing login (including 2FA if needed)...")
                if args.save_storage:
                    context.storage_state(path=str(storage_state_path))
                    print(f"Saved storage state to {storage_state_path}")

            print("\n" + "=" * 60)
            print(f"Starting to add {len(app_ids)} games to wishlist...")
            print(f"Rate limit: {args.rate_limit}s per game (to avoid IP ban)")
            print("=" * 60 + "\n")

            added, skipped, errors, failed_ids = add_to_wishlist(page, app_ids, args.rate_limit)

            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"Total games: {len(app_ids)}")
            print(f"Added: {added}")
            print(f"Skipped (already in wishlist): {skipped}")
            print(f"Errors: {errors}")
            print("=" * 60)
            print("Finished!")

            if failed_ids:
                error_path = Path(args.errors_file)
                with open(error_path, "w", encoding="utf-8") as f:
                    json.dump({"failed_app_ids": failed_ids}, f, indent=2)
                print(f"Failed app IDs saved to {error_path}")

            context.close()
            browser.close()

        except KeyboardInterrupt:
            print("\n\nProcess interrupted by user.")
        except Exception as e:
            print(f"\n\nFatal error: {e}")
            import traceback

            traceback.print_exc()
        finally:
            cleanup_temp_files(args.no_cleanup)


if __name__ == "__main__":
    main()
