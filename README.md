# Steam Wishlist Copier 🎮

Automatically copy a Steam wishlist from one account to another using modern Playwright automation.

## ✨ Features

- 📥 Download wishlist from any public Steam profile
- 🤖 Automatically add games to your wishlist
- ⏱️ Smart rate limiting to avoid IP bans
- 🔒 Handles age verification gates automatically
- ⏭️ Skips games already in your wishlist
- 📊 Detailed progress tracking and summary
- 🧪 Dry-run mode for testing without login
- 💾 Optional login storage state reuse
- 🧾 Failed app ID log for retry

## 📋 Requirements

- Python 3.9 or higher
- Chrome/Chromium browser (auto-installed by Playwright)

## 🚀 Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
python -m playwright install chromium
```

## 📖 Usage

### Basic Usage (Interactive)
```bash
python Start.py
```

### Test Mode (No Login Required) 🧪
Preview what games would be added without actually logging in:
```bash
python Start.py --dry-run --user <steam_user_id>
```

### Advanced Options
```bash
# Specify source user from command line
python Start.py --user <steam_user_id>

# Limit number of games (for testing)
python Start.py --user <steam_user_id> --limit 5

# Combine dry-run with limit
python Start.py --dry-run --user <steam_user_id> --limit 10

# Headless mode
python Start.py --user <steam_user_id> --headless

# Save and reuse login session
python Start.py --user <steam_user_id> --save-storage
python Start.py --user <steam_user_id> --storage-state steam_storage.json

# Tune rate limits and download concurrency
python Start.py --user <steam_user_id> --rate-limit 4 --download-delay 0.3 --download-workers 2

# Keep wishlist JSON files for debugging
python Start.py --user <steam_user_id> --no-cleanup
```

### Command Line Arguments

- `--dry-run`: Download and preview wishlist without logging in or adding games
- `--user <id>`: Specify source Steam user ID
- `--limit <n>`: Limit number of games to add (useful for testing)
- `--rate-limit <sec>`: Delay between add actions (default: 4)
- `--download-delay <sec>`: Delay between page downloads (default: 0.3)
- `--download-workers <n>`: Parallel download workers (default: 2)
- `--headless`: Run browser in headless mode
- `--storage-state <path>`: Path to Playwright storage state (default: steam_storage.json)
- `--save-storage`: Save storage state after login
- `--no-cleanup`: Keep downloaded wishlist JSON files
- `--errors-file <path>`: Where to save failed app IDs (default: wishlist_errors.json)
- `-h, --help`: Show help message

## ⚠️ Important Notes

- **Rate Limiting**: The script waits between each game addition to comply with Steam's rate limits and avoid IP bans
- **Public Wishlist**: The source user's wishlist must be set to public
- **2FA Support**: You'll need to complete two-factor authentication manually when prompted
- **Privacy**: Your password is never logged or displayed on screen
- **Estimated Time**: For 100 games at 4s per game, expect ~6-7 minutes of runtime

## 🔧 Troubleshooting

**"No games found in wishlist"**
- Ensure the source user's wishlist is set to public
- Verify the user ID is correct

**Browser doesn't open**
- Run `python -m playwright install chromium` again
- Check that you have Python 3.9+

**Rate limiting / IP ban**
- The script already includes delays between add actions
- If you get banned, wait 6-24 hours before trying again
- Don't reduce the `--rate-limit` too aggressively

## 🆕 What's New in 2025 Edition

- ✅ Migrated from Selenium to Playwright (faster, more reliable)
- ✅ Added `--dry-run` mode for testing without login
- ✅ Command-line arguments support
- ✅ Better error handling and progress reporting
- ✅ Updated rate limiting based on 2025 Steam API changes
- ✅ Cleaner code with better structure
- ✅ Fixed security issues (password no longer displayed)
- ✅ Storage state reuse for faster logins
- ✅ Failed item logging for retry

## 📝 Example Output

```
============================================================
Steam Wishlist Copier - Playwright Edition (2025)
============================================================
Downloading wishlist for user: example_user
Downloaded 2 pages with 47 games

============================================================
WISHLIST PREVIEW
============================================================
Total games to be added: 47

Estimated time: ~3.1 minutes
============================================================
```

## 📄 License

MIT License - Feel free to use and modify as needed.
