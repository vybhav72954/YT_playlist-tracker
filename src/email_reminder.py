import os, ast, smtplib
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- Load .env ---
load_dotenv()
EMAIL = os.getenv("SMTP_EMAIL")
PASSWORD = os.getenv("SMTP_PASSWORD")
contacts = ast.literal_eval(os.getenv("EMAIL_CONTACTS"))
PLAYLIST = os.getenv("PLAYLIST_NAME")

# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Open tracker
spreadsheet = client.open(os.getenv("SHEET_NAME"))
worksheet = spreadsheet.get_worksheet(0)

headers = worksheet.row_values(1)
url_col_idx = headers.index("Video URL") + 1
records = worksheet.get_all_records()
today = datetime.today().date()

overdue = {p: [] for p in contacts.keys()}

for i, row in enumerate(records, start=2):
    if row["Day"] == "Weekend":
        continue
    scheduled_date = datetime.fromisoformat(row["Date"]).date()
    if today > scheduled_date + timedelta(days=3):  # 3-day leeway
        for p in contacts:
            if not row[p]:  # if participant hasn't marked as done
                # Extract formula from cell
                formula = worksheet.cell(i, url_col_idx, value_render_option='FORMULA').value
                url = ""
                if formula and formula.startswith("=HYPERLINK"):
                    match = re.search(r'"(https?://[^"]+)"', formula)
                    if match:
                        url = match.group(1)

                overdue[p].append((row["Video Title"], row["Date"], url))

def send_email(to_email, subject, body_html):
    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    # Plain text fallback (optional)
    plain_text = "Please view this email in an HTML-compatible client."
    msg.attach(MIMEText(plain_text, "plain"))

    # Proper HTML part
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()  # upgrade to secure connection
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, to_email, msg.as_string())

for person, tasks in overdue.items():
    if tasks:
        subject = f"REMINDER - {PLAYLIST} - Missed Deadline"
        body_html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <p>Hello {person},</p>
            <p>This is a reminder that you are behind schedule on the following videos:</p>
            <ul>
        """
        for title, date, url in tasks:
            body_html += f"""
              <li>
                📺 <b>{title}</b> (was due on {date})<br>
                <a href="{url}" style="color: #1a73e8;">▶ Watch here</a>
              </li>
            """
        body_html += """
            </ul>
            <p>Take some time to catch up. Remember: We have a loan to repay!</p>
            <p>Cheers,<br><i>Am Watching You!</i></p>
          </body>
        </html>
        """

        send_email(contacts[person], subject, body_html)
        print(f"Email sent to {person}")
