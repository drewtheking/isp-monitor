import os
import smtplib
import gspread
import socket
import time
from oauth2client.service_account import ServiceAccountCredentials
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
    pst_timezone = timezone(timedelta(hours=8))
    return datetime.now(pst_timezone).strftime("%Y-%m-%d %I:%M %p")

def get_tcp_latency(ip, port):
    """
    Measures the time it takes to open a TCP connection.
    This bypasses ICMP/Ping blocks.
    """
    start_time = time.time()
    try:
        # Create a socket connection to the specific IP and Port from the sheet
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5) # 5 second timeout for international travel
        sock.connect((ip, port))
        sock.close()
        end_time = time.time()
        return (end_time - start_time) * 1000 # Return in milliseconds
    except Exception as e:
        print(f"TCP Connection failed for {ip}:{port} -> {e}")
        return None

def main():
    print(f"--- Starting TCP Monitor (PST: {get_pst_time()}) ---")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME).sheet1
    all_rows = sheet.get_all_values() 
    
    for i, row in enumerate(all_rows[1:], start=2):
        branch = row[0] #
        isp = row[1]    #
        raw_url = row[2] #
        
        if not raw_url or "." not in raw_url:
            continue

        try:
            # Extract IP and Port (e.g., 124.107.249.219 and 4444)
            ip_match = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', raw_url)
            port_match = re.search(r':(\d+)$', raw_url)
            
            if not ip_match or not port_match:
                continue
                
            clean_ip = ip_match.group()
            port = int(port_match.group(1))
            timestamp = get_pst_time()
            
            # MEASURE TCP LATENCY
            latency = get_tcp_latency(clean_ip, port)

            if latency is None:
                print(f"[{branch}] {clean_ip}:{port} - DOWN")
                sheet.update_cell(i, 5, f"DOWN @ {timestamp}") # Column E
            else:
                print(f"[{branch}] {clean_ip}:{port} - UP ({latency:.0f}ms)")
                # Log the actual latency to the sheet
                sheet.update_cell(i, 5, f"UP: {latency:.0f}ms @ {timestamp}")

        except Exception as e:
            print(f"!!! Error on row {i}: {e}")

if __name__ == "__main__":
    main()
