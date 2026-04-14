# 🇮🇪 Ireland Visa Decision Tracker

Automatically checks the Irish Embassy New Delhi visa decisions list every day at **11:10 AM IST**.

✅ **Safe for a public repository** — no credentials, no application numbers, nothing private is committed to this repo. Everything is stored as GitHub Secrets.

**Source page:** https://www.ireland.ie/en/india/newdelhi/services/visas/processing-times-and-decisions/

---

## How it works

1. Visits the Embassy New Delhi decisions page and finds today's `.ods` link (the filename changes daily — no hardcoded URL)
2. Downloads the file once
3. Searches for **each** application number supplied via the `APPLICATION_NUMBERS` secret
4. If a decision is found → sends a separate notification per application with **Approved** or **Refused**
5. If no decision yet → sends a **daily summary email** listing all pending applications so you know the check ran
6. All timestamps are shown in **IST (UTC+5:30)** regardless of server timezone

---

## Setup

### Step 1 — Fork or clone this repository

### Step 2 — Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret Name           | Format / Example                                                        | Required |
|-----------------------|-------------------------------------------------------------------------|----------|
| `APPLICATION_NUMBERS` | Comma-separated, e.g. `12345678,87654321`                              | ✅ Yes   |
| `GMAIL_USER`          | Your Gmail address, e.g. `you@gmail.com`                               | ✅ Yes   |
| `GMAIL_PASS`          | Gmail App Password (not your login password) — generate at https://myaccount.google.com/apppasswords | ✅ Yes   |
| `NOTIFY_EMAIL`        | One or more recipients, comma-separated, e.g. `you@gmail.com,friend@yahoo.com` | ✅ Yes   |
| `TELEGRAM_BOT_TOKEN`  | Telegram bot token from [@BotFather](https://t.me/BotFather)           | optional |
| `TELEGRAM_CHAT_ID`    | Your Telegram chat ID from [@userinfobot](https://t.me/userinfobot)    | optional |

> GitHub Secrets are **fully encrypted** and never exposed — even in a public repository.

### Step 3 — Test manually

Go to **Actions tab** → **Ireland Visa Decision Tracker** → **Run workflow** → click the green button.

---

## Schedule

Runs automatically every day at **11:10 AM IST** (05:40 UTC).

---

## Customisation

**Add or change application numbers** — update the `APPLICATION_NUMBERS` secret:
```
12345678,87654321,99999999
```

**Add or change recipient emails** — update the `NOTIFY_EMAIL` secret:
```
you@gmail.com,partner@gmail.com,parent@yahoo.com
```
Each address will receive its own individual email. No code changes needed.

**Change the schedule** — edit the cron line in `.github/workflows/visa-tracker-github-actions.yml`:
```yaml
- cron: "40 5 * * *"   # 11:10 AM IST = 05:40 UTC
```
Use [crontab.guru](https://crontab.guru) to convert IST to UTC.
