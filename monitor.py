import os
import smtplib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from ping3 import ping
from email.mime.text import MIMEText
from datetime import datetime
import json
import re

# --- CONFIGURATION ---
creds_json = os.environ.get("GDRIVE_API_CREDENTIALS")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL") 
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") 
SHEET_NAME = "SMTP AUTOMATION FOR STORE ASSIGN" 

def send_email(to_email, branch, isp, details):
    msg = MIMEText(details)
    msg['Subject'] = f"ISP ALERT: {branch} ({isp})"
    msg['From'] = SMTP_EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"!!! Email Error: {e}")

def main():
    print("--- Starting Monitor ---")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME).sheet1
    all_rows = sheet.get_all_values() 
    
    # We skip headers (Row 1)
    for i, row in enumerate(all_rows[1:], start=2):
        branch = row[0] # Column A
        isp = row[1]    # Column B
        raw_url = row[2] # Column C (e.g., https://124.107.249.219:4444)
        email_to = row[3] # Column D

        if not raw_url or "." not in raw_url:
            continue

        try:
            # CLEANING: Use regex to extract ONLY the IP address digits
            # This turns "https://124.107.249.219:4444" into "124.107.249.219"
            ip_match = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', raw_url)
            if not ip_match:
                print(f"Skipping row {i}: No valid IP found in '{raw_url}'")
                continue
            
            clean_ip = ip_match.group()
            print(f"Checking {branch} ({clean_ip})...")
            
            # PINGING
            response = ping(clean_ip, timeout=2)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            if response is None:
                print(f"  > RESULT: DOWN")
                sheet.update_cell(i, 5, f"DOWN @ {timestamp}") # Column E
                send_email(email_to, branch, isp, f"Unreachable: {clean_ip} (Pings allowed on Firewall but failing)")
            else:
                latency = response * 1000
                print(f"  > RESULT: {latency:.0f}ms")
                # Update the sheet so you know it's working
                sheet.update_cell(i, 5, f"OK: {latency:.0f}ms @ {timestamp}")

        except Exception as e:
            print(f"!!! Error on row {i}: {e}")

if __name__ == "__main__":
    main()
