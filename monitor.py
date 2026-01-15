import os
import smtplib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from ping3 import ping
from email.mime.text import MIMEText
from datetime import datetime
import json

# --- CONFIGURATION ---
# Load credentials from GitHub Secrets (we will set this up later)
creds_json = os.environ.get("GDRIVE_API_CREDENTIALS")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL") # Your email
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") # Your App Password
SHEET_NAME = "SMTP AUTOMATION FOR STORE ASSIGN" # Your specific sheet name

def send_email(to_email, branch, isp, ip):
    subject = f"DOWN ALERT: {branch} - {isp}"
    body = f"Connection Lost!\n\nBranch: {branch}\nISP: {isp}\nIP: {ip}\nTime: {datetime.now()}"
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_EMAIL
    msg['To'] = to_email

    try:
        # Assuming Gmail/Google Workspace. Change port to 587 if using TLS.
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    # Authenticate with Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    # Open the sheet
    sheet = client.open(SHEET_NAME).sheet1
    data = sheet.get_all_records() # Reads the whole sheet

    # Iterate through rows
    # Note: gspread uses 1-based indexing. Row 1 is headers.
    for i, row in enumerate(data, start=2): 
        raw_ip = row['ip'] # format: https://124.107...:4444
        branch = row['branch']
        isp = row['isp']
        email_recipient = row['email']

        # 1. CLEAN THE IP ADDRESS
        # We need to remove 'https://' and the port ':4444'
        try:
            # Splits by '//' to get '124.107...:4444', then splits by ':' to get just the IP
            clean_ip = raw_ip.split('//')[1].split(':')[0]
        except:
            print(f"Skipping invalid IP format: {raw_ip}")
            continue

        # 2. PING THE IP
        # timeout is in seconds
        response = ping(clean_ip, timeout=2) 

        status = "UP" if response is not None else "DOWN"
        print(f"Checking {branch} ({clean_ip})... Status: {status}")

        # 3. LOGIC: IF DOWN, CHECK IF WE NEED TO ALERT
        if status == "DOWN":
            # Optional: Check 'lastAlert' column to avoid spamming every 5 mins
            # For now, we just send the email.
            send_email(email_recipient, branch, isp, clean_ip)
            
            # Update the 'lastAlert' column (Column E is index 5)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.update_cell(i, 5, timestamp) 

if __name__ == "__main__":
    main()
