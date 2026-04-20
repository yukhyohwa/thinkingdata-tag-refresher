# thinkingdata-tag-refresher

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
SESSION_DIR=C:/path/to/thinkingdata-tag-refresher/ta_session
```

### 3. First Login (save session)

Run the following once so the script can save your browser session:

```bat
venv\Scripts\python.exe main.py --show
```

The browser will open visibly, log you in, and save the session. After this, subsequent runs will skip the login automatically.

### 4. Test Headless Mode

```bat
venv\Scripts\python.exe main.py
```

### 5. Schedule with Windows Task Scheduler

In **Task Scheduler**, create a new task:

| Field | Value |
|---|---|
| **Program/script** | `C:\path\to\thinkingdata-tag-refresher\run_refresh.bat` |
| **Start in** | `C:\path\to\thinkingdata-tag-refresher\` |
| **Trigger** | Set your preferred schedule (e.g. daily, hourly) |
| **Run whether user is logged on or not** | ✅ Highly Recommended (Runs in background) |

> [!IMPORTANT]
> **Prevention of Hanging Tasks:**
> To ensure the task doesn't get stuck if an instance fails to close:
> 1. Go to the **Settings** tab.
> 2. Set "If the task is already running..." to **"Stop the existing instance"**.
> 3. Check "Stop the task if it runs longer than" and set it to **1 hour**.

---

## CLI Options

```
python main.py             # Headless (default)
python main.py --show      # Open visible browser (for debugging)
python main.py --login     # Force re-login (clears old session)
python main.py --login --show  # Force re-login with visible browser
```

---

## Troubleshooting

- **Task Status is "Running" but no progress** → Check if `run_refresh.bat` contains a `pause` command (it should have been removed for automated tasks).
- **Refresh button not found** → Check `logs/` or run with `--show` to see what the page looks like.
- **Login fails** → Run `python main.py --login --show` to observe the login process visually.
- **Session expired** → Run `python main.py --login` to clear the old session and re-authenticate.
