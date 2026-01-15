import os
import smtplib
import gspread
import socket
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
    body = f"Network Alert!\n\nBranch: {branch}\nISP: {isp}\nDetails: {details}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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

def check_port(ip, port):
    """Checks if a specific TCP port is open."""
    try:
        with socket.create_connection((ip, port), timeout=3):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def main():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    
    # Read only necessary columns
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

        # Extract IP and Port from https://124.107.249.219:4444
        try:
            clean_ip = raw_ip_entry.split('//')[1].split(':')[0]
            port = int(raw_ip_entry.split(':')[-1])
        except:
            print(f"Skipping invalid format: {raw_ip_entry}")
            continue

        # 1. TRY TCP PORT CHECK (Most reliable for firewalled stores)
        is_port_open = check_port(clean_ip, port)
        
        # 2. TRY NORMAL ICMP PING AS BACKUP
        latency = ping(clean_ip, timeout=2)
        
        timestamp = datetime.now().strftime("%H:%M")

        if is_port_open:
            print(f"{branch}: Port {port} is OPEN (Online)")
            # If you want to clear the alert in the sheet when it's back up:
            # sheet.update_cell(i, 5, "ONLINE") 
        elif latency is not None:
            print(f"{branch}: Port closed, but Ping OK ({latency*1000:.0f}ms)")
        else:
            print(f"{branch}: UNREACHABLE (Port & Ping failed)")
            send_email(email_recipient, branch, isp, f"Unreachable at {clean_ip}:{port}", "OFFLINE")
            sheet.update_cell(i, 5, f"DOWN @ {timestamp}")

if __name__ == "__main__":
    main()
