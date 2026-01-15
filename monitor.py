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
    body = f"Network Status Update\n\nBranch: {branch}\nISP: {isp}\nDetails: {details}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Email failed: {e}")

def main():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    
    # Read Columns A to E
    list_of_lists = sheet.get('A1:E100') 
    headers = list_of_lists[0]
    data = [dict(zip(headers, row)) for row in list_of_lists[1:]]

    for i, row in enumerate(data, start=2): 
        raw_ip_entry = row.get('ip', '')
        branch = row.get('branch', 'Unknown')
        isp = row.get('isp', 'Unknown')
        email_recipient = row.get('email', '')

        if not raw_ip_entry:
            continue

        # 1. EXTRACT RAW PUBLIC IP ONLY
        try:
            # Converts "https://124.107.249.219:4444" -> "124.107.249.219"
            clean_ip = raw_ip_entry.split('//')[1].split(':')[0]
        except:
            continue

        # 2. PERFORM NORMAL PING (ICMP)
        # response_time is in seconds
        response_time = ping(clean_ip, timeout=2)
        timestamp = datetime.now().strftime("%H:%M")

        if response_time is None:
            # TOTAL DOWN
            print(f"{branch} ({clean_ip}): DOWN")
            sheet.update_cell(i, 5, f"DOWN @ {timestamp}")
            send_email(email_recipient, branch, isp, f"IP {clean_ip} is not responding to pings.", "OFFLINE")
        
        else:
            latency_ms = response_time * 1000
            if latency_ms > 100:
                # HIGH LATENCY
                print(f"{branch} ({clean_ip}): SLOW ({latency_ms:.0f}ms)")
                sheet.update_cell(i, 5, f"LATENCY: {latency_ms:.0f}ms @ {timestamp}")
                send_email(email_recipient, branch, isp, f"Latency is {latency_ms:.2f}ms (Threshold: 100ms)", "SPEED")
            else:
                # HEALTHY
                print(f"{branch} ({clean_ip}): OK ({latency_ms:.0f}ms)")
                # Optional: Uncomment below to clear the cell if the connection is now fine
                # sheet.update_cell(i, 5, "")

if __name__ == "__main__":
    main()
