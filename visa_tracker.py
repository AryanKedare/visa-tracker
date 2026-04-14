#!/usr/bin/env python3
"""
Ireland Visa Decision Tracker
Scrapes: ireland.ie/en/india/newdelhi/services/visas/processing-times-and-decisions/
Schedule: daily at 11:10 AM IST (05:40 UTC) via GitHub Actions

All credentials and application numbers are read from environment variables (GitHub Secrets).
Safe to use in a public repository - nothing sensitive is hardcoded.
"""

import subprocess
import sys
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# Install dependencies before any third-party imports
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "-q",
     "requests", "beautifulsoup4", "odfpy", "lxml"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

import requests
from bs4 import BeautifulSoup
from odf.opendocument import load as load_ods
from odf.table import Table, TableRow, TableCell
from odf.text import P
from odf.namespaces import TABLENS

# --- ALL CONFIG FROM GITHUB SECRETS (environment variables) ---
# APPLICATION_NUMBERS secret format: "12345678,87654321"
APPLICATION_NUMBERS = [n.strip() for n in os.environ.get("APPLICATION_NUMBERS", "").split(",") if n.strip()]

DECISIONS_PAGE_URL = "https://www.ireland.ie/en/india/newdelhi/services/visas/processing-times-and-decisions/"
ODS_FILE_PATH      = "/tmp/visa_decisions.ods"

NOTIFY_EMAIL       = os.environ.get("NOTIFY_EMAIL", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_PASS         = os.environ.get("GMAIL_PASS", "")


def get_latest_ods_url():
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VisaTracker/1.0)"}
    resp = requests.get(DECISIONS_PAGE_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.lower().endswith(".ods"):
            if href.startswith("http"):
                return href
            elif href.startswith("//"):
                return "https:" + href
            elif href.startswith("/"):
                return "https://www.ireland.ie" + href
            else:
                return "https://www.ireland.ie/" + href
    raise RuntimeError(
        f"No .ods file link found on: {DECISIONS_PAGE_URL}\n"
        "The page structure may have changed - check manually."
    )


def download_ods(ods_url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VisaTracker/1.0)"}
    resp = requests.get(ods_url, headers=headers, timeout=60)
    resp.raise_for_status()
    with open(ODS_FILE_PATH, "wb") as f:
        f.write(resp.content)
    print(f"  + Downloaded: {ods_url}")


def get_cell_text(cell):
    ps = cell.getElementsByType(P)
    return " ".join(
        (p.plainText() if hasattr(p, "plainText") else "".join(
            str(n) for n in p.childNodes if hasattr(n, "data")
        )).strip()
        for p in ps
    )


def load_all_rows():
    doc = load_ods(ODS_FILE_PATH)
    all_rows = []
    for sheet in doc.spreadsheet.getElementsByType(Table):
        for row in sheet.getElementsByType(TableRow):
            cells = row.getElementsByType(TableCell)
            row_values = []
            for cell in cells:
                repeat_attr = cell.attributes.get((TABLENS, "number-columns-repeated"))
                repeat = int(repeat_attr) if repeat_attr else 1
                text = get_cell_text(cell)
                row_values.extend([text] * repeat)
            all_rows.append(row_values)
    return all_rows


def search_application(all_rows, app_number):
    return [row for row in all_rows if app_number.upper() in " | ".join(row).upper()]


def classify_decision(row_values):
    combined = " ".join(row_values).lower()
    if any(w in combined for w in ["approved", "grant", "approve"]):
        return "APPROVED"
    if any(w in combined for w in ["refused", "refuse", "reject"]):
        return "REFUSED"
    return "FOUND (check manually)"


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        print("  + Telegram notification sent.")
    except Exception as e:
        print(f"  x Telegram failed: {e}")


def send_email(subject, body):
    if not NOTIFY_EMAIL or not GMAIL_USER or not GMAIL_PASS:
        print("  x Email skipped: NOTIFY_EMAIL / GMAIL_USER / GMAIL_PASS secrets not set.")
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = GMAIL_USER
        msg["To"] = NOTIFY_EMAIL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
        print("  + Email sent.")
    except Exception as e:
        print(f"  x Email failed: {e}")


def notify(subject, message):
    print(f"\n{'='*55}\n{message}\n{'='*55}")
    send_telegram(message)
    send_email(subject, message)


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M IST")

    if not APPLICATION_NUMBERS:
        print("  x No application numbers found. Set the APPLICATION_NUMBERS GitHub Secret.")
        return

    print(f"[{now}] Checking visa decisions for {len(APPLICATION_NUMBERS)} application(s)...")

    try:
        ods_url = get_latest_ods_url()
        print(f"  + Found decision list: {ods_url}")

        download_ods(ods_url)
        all_rows = load_all_rows()

        pending = []   # applications with no decision yet

        for app_number in APPLICATION_NUMBERS:
            matches = search_application(all_rows, app_number)
            if matches:
                for row in matches:
                    decision = classify_decision(row)
                    row_str = " | ".join(str(c) for c in row if str(c).strip())
                    message = (
                        f"Ireland Visa Decision Alert\n"
                        f"Application : {app_number}\n"
                        f"Decision    : {decision}\n"
                        f"Details     : {row_str}\n"
                        f"Source      : {ods_url}\n"
                        f"Checked at  : {now}"
                    )
                    notify(f"Visa Decision [{app_number}]: {decision}", message)
            else:
                pending.append(app_number)

        # Send a single daily summary for all pending applications
        if pending:
            pending_list = "\n".join(f"  - {n}" for n in pending)
            message = (
                f"Ireland Visa - No Decision Yet\n"
                f"The following applications have no decision as of today:\n"
                f"{pending_list}\n"
                f"Source     : {ods_url}\n"
                f"Checked at : {now}\n"
                f"Will check again tomorrow at 11:10 AM IST."
            )
            notify("Visa Tracker: No Decision Yet", message)

    except Exception as e:
        err_msg = (
            f"Ireland Visa Tracker ERROR\n"
            f"Error      : {e}\n"
            f"Checked at : {now}"
        )
        notify("Ireland Visa Tracker Error", err_msg)
        raise


if __name__ == "__main__":
    main()
