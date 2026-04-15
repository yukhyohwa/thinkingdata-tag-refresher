# fivecross-ta-tag-refresher

Automatically navigates to the ThinkingData tag management page, logs in if needed (using a persistent browser session), and clicks the **刷新 (Refresh)** button.

Designed to be run as a **Windows Scheduled Task**.

---

## Quick Start

### 1. First-time Setup

Double-click `setup.bat` — it will:
- Create a Python virtual environment (`venv/`)
- Install `playwright` and `python-dotenv`
- Download the Chromium browser

### 2. Configure Credentials

Edit `.env` and fill in your credentials:

```env
TA_URL=http://8.211.141.76:8993/
TA_USER=your_username
TA_PASS=your_password
TAG_URL=http://8.211.141.76:8993/#/tag/tag/1?currentProjectId=16
SESSION_DIR=C:/full/path/to/fivecross-ta-tag-refresher/ta_session
```

### 3. First Login (save session)

Run the following once so the script can save your browser session:

```bat
venv\Scripts\python.exe refresh_tag.py --show
```

The browser will open visibly, log you in, and save the session. After this, subsequent runs will skip the login automatically.

### 4. Test Headless Mode

```bat
venv\Scripts\python.exe refresh_tag.py
```

### 5. Schedule with Windows Task Scheduler

In **Task Scheduler**, create a new task:

| Field | Value |
|---|---|
| **Program/script** | `C:\path\to\fivecross-ta-tag-refresher\run_refresh.bat` |
| **Start in** | `C:\path\to\fivecross-ta-tag-refresher\` |
| **Trigger** | Set your preferred schedule (e.g. daily, hourly) |
| **Run whether user is logged on or not** | ✅ Check this |

---

## CLI Options

```
python refresh_tag.py             # Headless (default)
python refresh_tag.py --show      # Open visible browser (for debugging)
python refresh_tag.py --login     # Force re-login (clears old session)
python refresh_tag.py --login --show  # Force re-login with visible browser
```

---

## Troubleshooting

- **Refresh button not found** → A `debug_screenshot.png` is saved in the project folder. Open it to see what the page looks like.
- **Login fails** → Run `python refresh_tag.py --login --show` to observe the login process visually.
- **Session expired** → Run `python refresh_tag.py --login` to clear the old session and re-authenticate.
