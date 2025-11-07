import json
import time
import requests
import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# Constants
RATE_LIMIT_DELAY = 4  # seconds between requests (Steam rate limit: ~4 seconds per request in 2025)
TEMP_DIR = Path("temp_wishlist")
TIMEOUT = 10  # seconds for explicit waits


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


def setup_driver():
    """Initialize Chrome WebDriver with options."""
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    return webdriver.Chrome(options=options)


def login_to_steam(driver, username, password):
    """Log in to Steam account."""
    print("Navigating to Steam login page...")
    driver.get("https://store.steampowered.com/login/")

    try:
        wait = WebDriverWait(driver, TIMEOUT)

        # Wait for login form
        username_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
        )
        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")

        username_field.send_keys(username)
        password_field.send_keys(password)

        # Click login button
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()

        print("Login form submitted. Please complete any 2FA if required.")

    except (NoSuchElementException, TimeoutException) as e:
        print(f"Error during login: {e}")
        raise


def handle_age_gate(driver):
    """Handle age verification if present."""
    try:
        age_gate = driver.find_element(By.ID, "app_agegate")
        if age_gate.is_displayed():
            Select(driver.find_element(By.ID, "ageDay")).select_by_value("13")
            Select(driver.find_element(By.ID, "ageMonth")).select_by_value("April")
            Select(driver.find_element(By.ID, "ageYear")).select_by_value("1993")

            view_button = driver.find_element(By.ID, "view_product_page_btn")
            view_button.click()
            time.sleep(2)
            return True
    except NoSuchElementException:
        return False


def add_to_wishlist(driver, app_ids):
    """Add games to wishlist with proper rate limiting."""
    total = len(app_ids)
    added = 0
    skipped = 0
    errors = 0

    for idx, app_id in enumerate(app_ids, 1):
        print(f"[{idx}/{total}] Processing app ID: {app_id}")

        try:
            driver.get(f"https://store.steampowered.com/app/{app_id}")
            time.sleep(2)

            # Handle age gate
            handle_age_gate(driver)

            # Check if already in wishlist
            try:
                wishlist_area = driver.find_element(By.ID, "add_to_wishlist_area")
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
                    time.sleep(RATE_LIMIT_DELAY)

            except NoSuchElementException:
                print(f"  → Wishlist button not found, skipping")
                errors += 1

        except Exception as e:
            print(f"  → Error: {e}")
            errors += 1
            time.sleep(2)

    return added, skipped, errors


def main():
    """Main function."""
    print("=" * 50)
    print("Steam Wishlist Copier (Updated 2025)")
    print("=" * 50)

    # Get source wishlist
    source_user = input("Input user ID that you want to copy from: ").strip()
    app_ids = download_wishlist(source_user)

    if not app_ids:
        print("No games found in wishlist. Exiting.")
        return

    # Get login credentials
    print("\n" + "=" * 50)
    username = input("Input your Steam username: ").strip()
    password = input("Input your Steam password: ").strip()
    # SECURITY: Do NOT print password

    driver = None
    try:
        # Setup and login
        driver = setup_driver()
        login_to_steam(driver, username, password)

        input("\nPress Enter after completing login (including 2FA if needed)...")

        print("\n" + "=" * 50)
        print(f"Starting to add {len(app_ids)} games to wishlist...")
        print(f"Rate limit: {RATE_LIMIT_DELAY}s per game (to avoid IP ban)")
        print("=" * 50 + "\n")

        # Add games to wishlist
        added, skipped, errors = add_to_wishlist(driver, app_ids)

        # Summary
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)
        print(f"Total games: {len(app_ids)}")
        print(f"Added: {added}")
        print(f"Skipped (already in wishlist): {skipped}")
        print(f"Errors: {errors}")
        print("=" * 50)
        print("Finished!")

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
    finally:
        # Cleanup
        if driver:
            driver.quit()
        cleanup_temp_files()


if __name__ == "__main__":
    main()
