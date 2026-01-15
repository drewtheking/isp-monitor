import os
import smtplib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from ping3 import ping
from email.mime.text import MIMEText
from datetime import datetime
import json

# --- CONFIGURATION ---
creds_json = os.environ.get("GDRIVE_API_CREDENTIALS")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL") 
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") 
SHEET_NAME = "SMTP AUTOMATION FOR STORE ASSIGN" 

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
    print("--- Starting Monitor ---")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME).sheet1
    # Get all values as a list of lists to avoid header name issues
    all_rows = sheet.get_all_values() 
    
    # We skip the first row (headers)
    for i, row in enumerate(all_rows[1:], start=2):
        # row[0]=Branch, row[1]=ISP, row[2]=IP, row[3]=Email
        branch = row[0]
        isp = row[1]
        raw_ip_entry = row[2]
        email_recipient = row[3]

        if not raw_ip_entry or "https" not in raw_ip_entry:
            continue

        try:
            # Clean: https://124.107.249.219:4444 -> 124.107.249.219
            clean_ip = raw_ip_entry.split('//')[1].split(':')[0]
            
            print(f"Pinging {branch} at {clean_ip}...")
            response_time = ping(clean_ip, timeout=2)
            timestamp = datetime.now().strftime("%H:%M")

            if response_time is None:
                print(f" RESULT: DOWN")
                sheet.update_cell(i, 5, f"DOWN @ {timestamp}") # Column E
                send_email(email_recipient, branch, isp, f"Unreachable: {clean_ip}")
            else:
                latency = response_time * 1000
                if latency > 100:
                    print(f" RESULT: SLOW ({latency:.0f}ms)")
                    sheet.update_cell(i, 5, f"SLOW: {latency:.0f}ms @ {timestamp}")
                    send_email(email_recipient, branch, isp, f"High Latency: {latency:.2f}ms")
                else:
                    print(f" RESULT: OK ({latency:.0f}ms)")
                    # Clear the cell so you know it's currently healthy
                    sheet.update_cell(i, 5, "OK") 

        except Exception as e:
            print(f" Error processing row {i}: {e}")

if __name__ == "__main__":
    main()
