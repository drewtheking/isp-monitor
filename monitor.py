import os
import smtplib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from ping3 import ping
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
import json
import re

# --- CONFIGURATION ---
creds_json = os.environ.get("GDRIVE_API_CREDENTIALS")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL") 
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") 
SHEET_NAME = "SMTP AUTOMATION FOR STORE ASSIGN" 

def get_pst_time():
    # GitHub runners use UTC by default. This forces UTC+8 (Manila Time).
    pst_timezone = timezone(timedelta(hours=8))
    return datetime.now(pst_timezone).strftime("%Y-%m-%d %I:%M %p")

def send_email(to_email, branch, isp, details):
    msg = MIMEText(details)
    msg['Subject'] = f"NETWORK ALERT: {branch} ({isp})"
    msg['From'] = SMTP_EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"!!! Email Error: {e}")

def main():
    print(f"--- Starting Monitor (PST: {get_pst_time()}) ---")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME).sheet1
    all_rows = sheet.get_all_values() 
    
    for i, row in enumerate(all_rows[1:], start=2):
        branch = row[0] # Column A
        isp = row[1]    # Column B
        raw_url = row[2] # Column C
        email_to = row[3] # Column D

        if not raw_url or "." not in raw_url:
            continue

        try:
            # Clean: Extract only the IP address
            ip_match = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', raw_url)
            if not ip_match:
                continue
            
            clean_ip = ip_match.group()
            timestamp = get_pst_time()
            
            # PINGING
            response = ping(clean_ip, timeout=3) # Increased timeout to 3s for international lag

            if response is None:
                print(f"[{branch}] {clean_ip} is DOWN")
                # Updated column E
                sheet.update_cell(i, 5, f"DOWN @ {timestamp}") 
                send_email(email_to, branch, isp, f"Unreachable: {clean_ip} at {timestamp}")
            else:
                latency = response * 1000
                print(f"[{branch}] {clean_ip} is UP ({latency:.0f}ms)")
                sheet.update_cell(i, 5, f"UP: {latency:.0f}ms @ {timestamp}")

        except Exception as e:
            print(f"!!! Error on row {i}: {e}")

if __name__ == "__main__":
    main()
