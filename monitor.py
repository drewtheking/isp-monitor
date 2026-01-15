import os
import smtplib
import gspread
import socket
from oauth2client.service_account import ServiceAccountCredentials
from email.mime.text import MIMEText
from datetime import datetime
import json

# --- CONFIGURATION ---
creds_json = os.environ.get("GDRIVE_API_CREDENTIALS")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL") 
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") 
SHEET_NAME = "SMTP AUTOMATION FOR STORE ASSIGN" 

def send_email(to_email, branch, isp, ip_port):
    subject = f"OFFLINE ALERT: {branch} ({isp})"
    body = f"Connection unreachable!\n\nBranch: {branch}\nISP: {isp}\nTarget: {ip_port}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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

def is_reachable(ip, port):
    """Checks if a TCP port is reachable (bypass ICMP/Ping blocks)."""
    try:
        # 5 second timeout to be sure
        with socket.create_connection((ip, port), timeout=5):
            return True
    except:
        return False

def main():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    
    # Get only Columns A to E to avoid duplicate header errors
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

        # Extract IP and Port from format: https://124.107.249.219:4444
        try:
            # Cleans the "https://" and splits the IP from the Port
            clean_ip = raw_ip_entry.split('//')[1].split(':')[0]
            port = int(raw_ip_entry.split(':')[-1])
        except Exception as e:
            print(f"Error parsing IP {raw_ip_entry}: {e}")
            continue

        # PERFORM REACHABILITY CHECK
        print(f"Testing {branch} ({clean_ip}:{port})...", end=" ")
        
        if is_reachable(clean_ip, port):
            print("ONLINE")
            # Clear the alert cell if it was previously DOWN
            # sheet.update_cell(i, 5, "") 
        else:
            print("OFFLINE")
            timestamp = datetime.now().strftime("%H:%M")
            sheet.update_cell(i, 5, f"DOWN @ {timestamp}")
            send_email(email_recipient, branch, isp, f"{clean_ip}:{port}")

if __name__ == "__main__":
    main()
