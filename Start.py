"""
Steam Wishlist Copier - Playwright Version (2025)
Automatically copy a Steam wishlist from one account to another.
"""
import json
import time
import requests
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Constants
RATE_LIMIT_DELAY = 4  # seconds between requests (Steam rate limit: ~4 seconds per request in 2025)
TEMP_DIR = Path("temp_wishlist")
TIMEOUT = 10000  # milliseconds for Playwright waits


def download_wishlist(user_id):
    """Download all wishlist pages from a Steam user."""
    print(f"Downloading wishlist for user: {user_id}")
    TEMP_DIR.mkdir(exist_ok=True)

    wishlist_data = {}
    page = 0

    while True:
        print(f"Downloading page {page}...")
        try:
            response = requests.get(
                f"https://store.steampowered.com/wishlist/id/{user_id}/wishlistdata/?p={page}",
                timeout=30
            )
            response.raise_for_status()
            json_data = response.json()

            if not json_data:
                break

            # Save individual page
            file_path = TEMP_DIR / f"wishlist{page}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

            wishlist_data.update(json_data)
            page += 1
            time.sleep(1)  # Rate limiting for downloads

        except requests.RequestException as e:
            print(f"Error downloading page {page}: {e}")
            break

    print(f"Downloaded {page} pages with {len(wishlist_data)} games")
    return list(wishlist_data.keys())


def cleanup_temp_files():
    """Remove temporary wishlist JSON files."""
    if TEMP_DIR.exists():
        for file in TEMP_DIR.glob("wishlist*.json"):
            file.unlink()
        TEMP_DIR.rmdir()
        print("Temporary files cleaned up")


def login_to_steam(page, username, password):
    """Log in to Steam account."""
    print("Navigating to Steam login page...")
    page.goto("https://store.steampowered.com/login/", wait_until="domcontentloaded")

    try:
        # Wait for and fill login form
        page.wait_for_selector("input[type='text']", timeout=TIMEOUT)

        username_field = page.locator("input[type='text']").first
        password_field = page.locator("input[type='password']").first

        username_field.fill(username)
        password_field.fill(password)

        # Click login button
        login_button = page.locator("button[type='submit']").first
        login_button.click()

        print("Login form submitted. Please complete any 2FA if required.")

    except PlaywrightTimeout as e:
        print(f"Error during login: {e}")
        raise


def handle_age_gate(page):
    """Handle age verification if present."""
    try:
        age_gate = page.locator("#app_agegate")
        if age_gate.is_visible(timeout=2000):
            # Fill age verification
            page.select_option("#ageDay", "13")
            page.select_option("#ageMonth", "April")
            page.select_option("#ageYear", "1993")

            # Click view page button
            page.locator("#view_product_page_btn").click()
            page.wait_for_load_state("domcontentloaded")
            return True
    except:
        return False


def add_to_wishlist(page, app_ids):
    """Add games to wishlist with proper rate limiting."""
    total = len(app_ids)
    added = 0
    skipped = 0
    errors = 0

    for idx, app_id in enumerate(app_ids, 1):
        print(f"[{idx}/{total}] Processing app ID: {app_id}")

        try:
            page.goto(f"https://store.steampowered.com/app/{app_id}", wait_until="domcontentloaded")
            page.wait_for_timeout(1000)  # Wait for page to settle

            # Handle age gate
            handle_age_gate(page)

            # Check if already in wishlist
            try:
                wishlist_area = page.locator("#add_to_wishlist_area")

                # Wait for element to be available
                wishlist_area.wait_for(timeout=5000)

                # Check if already in wishlist (element has display: none)
                style = wishlist_area.get_attribute("style")

                if style and "display: none" in style:
                    print(f"  → Already in wishlist, skipping")
                    skipped += 1
                else:
                    # Add to wishlist
                    wishlist_area.click()
                    added += 1
                    print(f"  → Added to wishlist")

                    # IMPORTANT: Rate limiting to avoid IP ban (4 seconds per request in 2025)
                    page.wait_for_timeout(RATE_LIMIT_DELAY * 1000)

            except PlaywrightTimeout:
                print(f"  → Wishlist button not found, skipping")
                errors += 1

        except Exception as e:
            print(f"  → Error: {e}")
            errors += 1
            page.wait_for_timeout(2000)

    return added, skipped, errors


def show_wishlist_preview(app_ids):
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
    print(f"Estimated time: ~{len(app_ids) * RATE_LIMIT_DELAY / 60:.1f} minutes")
    print("=" * 60)


def main():
    """Main function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Steam Wishlist Copier - Automatically copy wishlists between Steam accounts"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download and preview wishlist without logging in or adding games"
    )
    parser.add_argument(
        "--user",
        type=str,
        help="Source Steam user ID to copy wishlist from"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of games to add (useful for testing)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Steam Wishlist Copier - Playwright Edition (2025)")
    print("=" * 60)

    # Get source wishlist
    if args.user:
        source_user = args.user
    else:
        source_user = input("Input user ID that you want to copy from: ").strip()

    app_ids = download_wishlist(source_user)

    if not app_ids:
        print("No games found in wishlist. Exiting.")
        return

    # Apply limit if specified
    if args.limit:
        print(f"\nLimiting to first {args.limit} games (--limit flag)")
        app_ids = app_ids[:args.limit]

    # Dry-run mode: just show what would be added
    if args.dry_run:
        print("\n🧪 DRY-RUN MODE - No games will be added")
        show_wishlist_preview(app_ids)
        print("\nTo actually add these games, run without --dry-run flag")
        cleanup_temp_files()
        return

    # Show preview
    show_wishlist_preview(app_ids)

    # Get login credentials
    print("\n" + "=" * 60)
    username = input("Input your Steam username: ").strip()
    password = input("Input your Steam password: ").strip()
    # SECURITY: Do NOT print password

    with sync_playwright() as p:
        try:
            # Launch browser (use headless=False to see the browser)
            print("\nLaunching browser...")
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()

            # Login to Steam
            login_to_steam(page, username, password)

            input("\nPress Enter after completing login (including 2FA if needed)...")

            print("\n" + "=" * 60)
            print(f"Starting to add {len(app_ids)} games to wishlist...")
            print(f"Rate limit: {RATE_LIMIT_DELAY}s per game (to avoid IP ban)")
            print("=" * 60 + "\n")

            # Add games to wishlist
            added, skipped, errors = add_to_wishlist(page, app_ids)

            # Summary
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"Total games: {len(app_ids)}")
            print(f"Added: {added}")
            print(f"Skipped (already in wishlist): {skipped}")
            print(f"Errors: {errors}")
            print("=" * 60)
            print("Finished!")

            # Close browser
            context.close()
            browser.close()

        except KeyboardInterrupt:
            print("\n\nProcess interrupted by user.")
        except Exception as e:
            print(f"\n\nFatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            cleanup_temp_files()


if __name__ == "__main__":
    main()
