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

def send_email(to_email, branch, isp, details, status_type):
    subject = f"{status_type} ALERT: {branch} ({isp})"
    body = f"Network Alert Triggered!\n\nBranch: {branch}\nISP: {isp}\nDetails: {details}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_EMAIL
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open(SHEET_NAME).sheet1
    
    # FIX: Get only Columns A to E to avoid "Duplicate Header" errors
    list_of_lists = sheet.get('A1:E100') 
    headers = list_of_lists[0]
    data = [dict(zip(headers, row)) for row in list_of_lists[1:]]

    for i, row in enumerate(data, start=2): 
        raw_ip = row.get('ip', '')
        branch = row.get('branch', 'Unknown')
        isp = row.get('isp', 'Unknown')
        email_recipient = row.get('email', '')

        if not raw_ip:
            continue

        # 1. CLEAN THE IP ADDRESS
        try:
            clean_ip = raw_ip.split('//')[1].split(':')[0]
        except:
            print(f"Skipping invalid IP: {raw_ip}")
            continue

        # 2. MEASURE LATENCY (In seconds)
        response_time = ping(clean_ip, timeout=2) 

        # 3. LOGIC: DOWN OR SLOW (>100ms)
        timestamp = datetime.now().strftime("%H:%M")
        
        if response_time is None:
            print(f"Checking {branch}... DOWN")
            send_email(email_recipient, branch, isp, f"No response from {clean_ip}", "DOWN")
            sheet.update_cell(i, 5, f"DOWN @ {timestamp}")

        else:
            latency_ms = response_time * 1000 # Convert to ms
            
            if latency_ms > 100:
                print(f"Checking {branch}... SLOW ({latency_ms:.0f}ms)")
                details = f"Latency to Store IP ({clean_ip}) is {latency_ms:.2f}ms. Connections to Apple.com will be degraded."
                send_email(email_recipient, branch, isp, details, "LATENCY")
                sheet.update_cell(i, 5, f"SLOW: {latency_ms:.0f}ms @ {timestamp}")
            else:
                print(f"Checking {branch}... OK ({latency_ms:.0f}ms)")
                # Optional: Clear cell if healthy
                # sheet.update_cell(i, 5, "")

if __name__ == "__main__":
    main()
