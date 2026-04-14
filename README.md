# 🇮🇪 Ireland Visa Decision Tracker

Automatically checks the Irish Embassy New Delhi visa decisions list every day at **11:10 AM IST**.

✅ **Safe for a public repository** — no credentials, no application numbers, nothing private is committed to this repo. Everything is stored as GitHub Secrets.

**Source page:** https://www.ireland.ie/en/india/newdelhi/services/visas/processing-times-and-decisions/

---

## How it works

1. Visits the Embassy New Delhi decisions page and finds today's `.ods` link (the filename changes daily)
2. Downloads the file once
3. Searches for each application number supplied via the `APPLICATION_NUMBERS` secret
4. If found → sends a separate **email** and/or **Telegram** notification with **Approved ✅** or **Refused ❌**
5. If not found → logs "No decision yet" and retries the next day

---

## Setup

### Step 1 — Fork or clone this repository

### Step 2 — Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret Name           | Value                                                                  | Required |
|-----------------------|------------------------------------------------------------------------|----------|
| `APPLICATION_NUMBERS` | Comma-separated numbers, e.g. `12345678,87654321`                     | ✅ Yes   |
| `GMAIL_USER`          | Your Gmail address                                                     | ✅ Yes   |
| `GMAIL_PASS`          | Gmail App Password from https://myaccount.google.com/apppasswords      | ✅ Yes   |
| `NOTIFY_EMAIL`        | Email address to receive alerts                                        | ✅ Yes   |
| `TELEGRAM_BOT_TOKEN`  | Telegram bot token from [@BotFather](https://t.me/BotFather)          | optional |
| `TELEGRAM_CHAT_ID`    | Your Telegram chat ID from [@userinfobot](https://t.me/userinfobot)   | optional |

> GitHub Secrets are **fully encrypted** and never exposed — even in a public repository.

### Step 3 — Test manually

Go to **Actions tab** → **Ireland Visa Decision Tracker** → **Run workflow** → click the green button.

---

## Schedule

Runs automatically every day at **11:10 AM IST** (05:40 UTC).
