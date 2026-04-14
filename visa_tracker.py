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
from datetime import datetime, timezone, timedelta

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

# IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

# --- ALL CONFIG FROM GITHUB SECRETS (environment variables) ---
# APPLICATION_NUMBERS secret format: "12345678,87654321"
APPLICATION_NUMBERS = [n.strip() for n in os.environ.get("APPLICATION_NUMBERS", "").split(",") if n.strip()]

# NOTIFY_EMAIL secret format: "a@gmail.com,b@gmail.com,c@yahoo.com"
NOTIFY_EMAILS = [e.strip() for e in os.environ.get("NOTIFY_EMAIL", "").split(",") if e.strip()]

DECISIONS_PAGE_URL = "https://www.ireland.ie/en/india/newdelhi/services/visas/processing-times-and-decisions/"
ODS_FILE_PATH      = "/tmp/visa_decisions.ods"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_PASS         = os.environ.get("GMAIL_PASS", "")


def mask_email(email):
    """For logs only: ar***@gmail.com"""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return local[:2] + "***@" + domain


def mask_app_number(number):
    """For logs only: ****4462"""
    return "****" + number[-4:] if len(number) >= 4 else "****"


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
    if not NOTIFY_EMAILS or not GMAIL_USER or not GMAIL_PASS:
        print("  x Email skipped: NOTIFY_EMAIL / GMAIL_USER / GMAIL_PASS secrets not set.")
        return
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            for recipient in NOTIFY_EMAILS:
                msg = MIMEText(body)
                msg["Subject"] = subject
                msg["From"] = GMAIL_USER
                msg["To"] = recipient
                server.sendmail(GMAIL_USER, recipient, msg.as_string())
                # Mask in logs only
                print(f"  + Email sent to {mask_email(recipient)}.")
    except Exception as e:
        print(f"  x Email failed: {e}")


def notify(log_subject, log_message, email_subject, email_message):
    """log_* versions are masked for console; email_* versions have full details."""
    print(f"\n{'='*55}\n{log_message}\n{'='*55}")
    send_telegram(email_message)
    send_email(email_subject, email_message)


def main():
    # Always use IST (UTC+5:30) regardless of GitHub Actions server timezone (UTC)
    now = datetime.now(tz=IST).strftime("%Y-%m-%d %I:%M %p IST")

    if not APPLICATION_NUMBERS:
        print("  x No application numbers found. Set the APPLICATION_NUMBERS GitHub Secret.")
        return

    masked_apps   = ", ".join(mask_app_number(n) for n in APPLICATION_NUMBERS)
    masked_emails = ", ".join(mask_email(e) for e in NOTIFY_EMAILS)

    # Logs: masked
    print(f"[{now}] Checking visa decisions for {len(APPLICATION_NUMBERS)} application(s): {masked_apps}")
    print(f"  + Notifying {len(NOTIFY_EMAILS)} recipient(s): {masked_emails}")

    try:
        ods_url = get_latest_ods_url()
        print(f"  + Found decision list: {ods_url}")

        download_ods(ods_url)
        all_rows = load_all_rows()

        pending = []

        for app_number in APPLICATION_NUMBERS:
            matches = search_application(all_rows, app_number)
            if matches:
                for row in matches:
                    decision = classify_decision(row)
                    row_str = " | ".join(str(c) for c in row if str(c).strip())

                    # Log: masked
                    log_msg = (
                        f"Ireland Visa Decision Alert\n"
                        f"Application : {mask_app_number(app_number)}\n"
                        f"Decision    : {decision}\n"
                        f"Checked at  : {now}"
                    )
                    # Email: full details
                    email_msg = (
                        f"Ireland Visa Decision Alert\n"
                        f"Application : {app_number}\n"
                        f"Decision    : {decision}\n"
                        f"Details     : {row_str}\n"
                        f"Source      : {ods_url}\n"
                        f"Checked at  : {now}"
                    )
                    notify(
                        log_subject=f"Visa Decision [{mask_app_number(app_number)}]: {decision}",
                        log_message=log_msg,
                        email_subject=f"Visa Decision [{app_number}]: {decision}",
                        email_message=email_msg
                    )
            else:
                pending.append(app_number)

        if pending:
            # Log: masked
            log_pending   = "\n".join(f"  - {mask_app_number(n)}" for n in pending)
            # Email: full numbers
            email_pending = "\n".join(f"  - {n}" for n in pending)

            log_msg = (
                f"Ireland Visa - No Decision Yet\n"
                f"Applications with no decision as of today:\n"
                f"{log_pending}\n"
                f"Checked at : {now}"
            )
            email_msg = (
                f"Ireland Visa - No Decision Yet\n"
                f"The following applications have no decision as of today:\n"
                f"{email_pending}\n"
                f"Source     : {ods_url}\n"
                f"Checked at : {now}\n"
                f"Will check again tomorrow at 11:10 AM IST."
            )
            notify(
                log_subject="Visa Tracker: No Decision Yet",
                log_message=log_msg,
                email_subject="Visa Tracker: No Decision Yet",
                email_message=email_msg
            )

    except Exception as e:
        err_msg = (
            f"Ireland Visa Tracker ERROR\n"
            f"Error      : {e}\n"
            f"Checked at : {now}"
        )
        notify(
            log_subject="Ireland Visa Tracker Error",
            log_message=err_msg,
            email_subject="Ireland Visa Tracker Error",
            email_message=err_msg
        )
        raise


if __name__ == "__main__":
    main()
