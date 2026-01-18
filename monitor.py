import os
import smtplib
import gspread
import socket
import time
import re
import json
from oauth2client.service_account import ServiceAccountCredentials
from ping3 import ping
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

# --- CONFIGURATION ---
creds_json = os.environ.get("GDRIVE_API_CREDENTIALS")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL") 
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") 
SHEET_NAME = "SMTP AUTOMATION FOR STORE ASSIGN" 

def get_pst_time():
    pst_timezone = timezone(timedelta(hours=8))
    return datetime.now(pst_timezone).strftime("%Y-%m-%d %I:%M %p")

def get_tcp_latency(ip, port):
    """Fallback: Measures time for a TCP handshake if ICMP is blocked."""
    start = time.time()
    try:
        with socket.create_connection((ip, port), timeout=3):
            return (time.time() - start) * 1000
    except:
        return None

def main():
    print(f"--- Dual-Mode Monitor Started (PST: {get_pst_time()}) ---")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME).sheet1
    all_rows = sheet.get_all_values() 
    
    for i, row in enumerate(all_rows[1:], start=2):
        branch, isp, raw_url = row[0], row[1], row[2] #
        
        if not raw_url or "." not in raw_url:
            continue

        try:
            # Extract IP and Port (e.g., 124.107.249.219 and 4444)
            ip_match = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', raw_url)
            port_match = re.search(r':(\d+)$', raw_url)
            
            if not ip_match or not port_match:
                continue
                
            ip, port = ip_match.group(), int(port_match.group(1))
            timestamp = get_pst_time()
            
            # TEST 1: Standard ICMP Ping
            latency = ping(ip, timeout=2)
            method = "ICMP"

            # TEST 2: Fallback to TCP if Ping fails (ISP might block International ICMP)
            if latency is None:
                latency = get_tcp_latency(ip, port)
                method = "TCP"

            if latency is None:
                print(f"[{branch}] {ip} - STILL DOWN")
                sheet.update_cell(i, 5, f"DOWN @ {timestamp}") # Column E
            else:
                print(f"[{branch}] {ip} - UP via {method} ({latency:.0f}ms)")
                sheet.update_cell(i, 5, f"UP: {latency:.0f}ms @ {timestamp}")

        except Exception as e:
            print(f"!!! Error row {i}: {e}")

if __name__ == "__main__":
    main()
