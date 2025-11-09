import os, ast, smtplib
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('reminder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("=" * 50)
logger.info(f"Script started at {datetime.now()}")

load_dotenv()

# Validate required environment variables
required_vars = ["SMTP_EMAIL", "SMTP_PASSWORD", "EMAIL_CONTACTS", "PLAYLIST_NAME", "SHEET_NAME"]
missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    logger.error(f"Missing required environment variables: {', '.join(missing)}")
    raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

EMAIL = os.getenv("SMTP_EMAIL")
PASSWORD = os.getenv("SMTP_PASSWORD")
PLAYLIST = os.getenv("PLAYLIST_NAME")

try:
    contacts = ast.literal_eval(os.getenv("EMAIL_CONTACTS"))
except Exception as e:
    logger.error(f"Failed to parse EMAIL_CONTACTS: {e}")
    raise

# Get configuration with defaults
REMINDER_DAYS = [int(d.strip()) for d in os.getenv("REMINDER_DAYS", "1,4").split(",")]
LEEWAY_DAYS = int(os.getenv("LEEWAY_DAYS", "3"))
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower()=="true"
DRY_RUN = os.getenv("DRY_RUN", "false").lower()=="true"

if DRY_RUN:
    logger.info("DRY RUN MODE - No emails will be sent")

logger.info(f"Configuration: REMINDER_DAYS={REMINDER_DAYS}, LEEWAY_DAYS={LEEWAY_DAYS}, EMAIL_ENABLED={EMAIL_ENABLED}")

# Check if emails are enabled
if not EMAIL_ENABLED:
    logger.info("Emails disabled in configuration. Exiting.")
    exit(0)

# Check if today is a reminder day (for weekly digest)
today_weekday = datetime.today().weekday()
if today_weekday not in REMINDER_DAYS:
    logger.info(
        f"Today is {datetime.today().strftime('%A')} (weekday {today_weekday}). Not a reminder day (configured: {REMINDER_DAYS}). Exiting.")
    exit(0)

logger.info(f"Today is a reminder day ({datetime.today().strftime('%A')}). Proceeding with checks...")

# Connect to Google Sheets
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    logger.info("Successfully authenticated with Google Sheets")
except Exception as e:
    logger.error(f"Failed to authenticate with Google: {e}")
    raise

try:
    spreadsheet = client.open(os.getenv("SHEET_NAME"))
    worksheet = spreadsheet.get_worksheet(0)
    logger.info(f"Opened spreadsheet: {os.getenv('SHEET_NAME')}")
except Exception as e:
    logger.error(f"Failed to open spreadsheet: {e}")
    raise

headers = worksheet.row_values(1)
url_col_idx = headers.index("Video URL") + 1
records = worksheet.get_all_records()
today = datetime.today().date()

logger.info(f"Processing {len(records)} records from sheet")

overdue = {p:[] for p in contacts.keys()}
total_videos = {p:0 for p in contacts.keys()}
completed_videos = {p:0 for p in contacts.keys()}

for i, row in enumerate(records, start=2):
    if row["Day"]=="Weekend":
        continue

    scheduled_date = datetime.fromisoformat(row["Date"]).date()

    for p in contacts:
        total_videos[p] += 1

        # Check if participant marked as done
        status = str(row.get(p, "")).strip().lower()
        if status=="done":
            completed_videos[p] += 1
        elif today > scheduled_date + timedelta(days=LEEWAY_DAYS):
            # Video is overdue (past leeway period)
            try:
                # Extract formula from cell
                formula = worksheet.cell(i, url_col_idx, value_render_option='FORMULA').value
                url = ""
                if formula and formula.startswith("=HYPERLINK"):
                    match = re.search(r'"(https?://[^"]+)"', formula)
                    if match:
                        url = match.group(1)

                overdue[p].append((row["Video Title"], row["Date"], url, status))
            except Exception as e:
                logger.warning(f"Failed to extract URL for row {i}: {e}")
                overdue[p].append((row["Video Title"], row["Date"], "", status))

logger.info(f"Overdue videos found: {sum(len(tasks) for tasks in overdue.values())}")


def send_email(to_email, subject, body_html):
    """Send email with error handling"""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        plain_text = "Please view this email in an HTML-compatible client."
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(EMAIL, PASSWORD)
            server.sendmail(EMAIL, to_email, msg.as_string())

        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(f"Authentication failed for {to_email} - check SMTP credentials")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending to {to_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending to {to_email}: {e}")
        return False


def create_progress_html(person, tasks, total, completed):
    """Create rich HTML email with progress tracking"""
    progress_pct = (completed / total * 100) if total > 0 else 0

    progress_bar = f"""
    <div style="background: #f0f0f0; border-radius: 10px; height: 25px; margin: 20px 0;">
        <div style="background: linear-gradient(90deg, #4CAF50, #8BC34A); 
                    width: {progress_pct}%; height: 100%; border-radius: 10px; 
                    line-height: 25px; text-align: center; color: white; font-weight: bold;">
            {progress_pct:.1f}%
        </div>
    </div>
    """

    body_html = f"""
    <html>
      <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; padding: 20px; background: #f9f9f9;">
        <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
          <h2 style="color: #1a73e8; border-bottom: 3px solid #1a73e8; padding-bottom: 10px;">
            🎓 {PLAYLIST} - Weekly Progress Report
          </h2>

          <p>Hey {person}!</p>

          <p style="font-size: 16px;">You've completed <b>{completed}/{total}</b> videos so far:</p>
          {progress_bar}
    """

    if tasks:
        body_html += f"""
          <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #856404;">Videos Behind Schedule ({len(tasks)})</h3>
            <ul style="padding-left: 20px;">
        """

        for title, date, url, status in tasks:
            days_overdue = (datetime.today().date() - datetime.fromisoformat(date).date()).days
            status_display = f" - Status: <i>{status}</i>" if status else ""

            body_html += f"""
              <li style="margin: 15px 0;">
                <b>{title}</b><br>
                <span style="color: #dc3545;">Due: {date} ({days_overdue} days overdue){status_display}</span><br>
            """

            if url:
                body_html += f"""
                <a href="{url}" style="display: inline-block; margin-top: 5px; padding: 8px 15px; 
                   background: #1a73e8; color: white; text-decoration: none; border-radius: 5px;">
                   Watch Now
                </a>
                """

            body_html += "</li>"

        body_html += """
            </ul>
          </div>
        """
    else:
        body_html += """
          <div style="background: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #155724;">Great Job!</h3>
            <p>You're all caught up! No overdue videos.</p>
          </div>
        """

    body_html += f"""
          <p style="font-size: 14px; color: #666; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
            <i>Remember: Consistency beats intensity. Keep going!</i>
          </p>

          <p style="font-size: 12px; color: #999;">
            This is an automated weekly reminder sent every {', '.join([['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][d] for d in REMINDER_DAYS])}.<br>
            Leeway period: {LEEWAY_DAYS} days
          </p>
        </div>
      </body>
    </html>
    """

    return body_html


# Send emails
emails_sent = 0
emails_failed = 0

for person, tasks in overdue.items():
    # Send weekly digest regardless of overdue status
    total = total_videos[person]
    completed = completed_videos[person]

    if total==0:
        logger.warning(f"No videos found for {person}, skipping email")
        continue

    subject = f"{PLAYLIST} - Weekly Update"
    if tasks:
        subject += f" - {len(tasks)} videos need attention"

    body_html = create_progress_html(person, tasks, total, completed)

    if DRY_RUN:
        logger.info(f"DRY RUN: Would send email to {person} ({contacts[person]})")
        logger.info(f"  - Completed: {completed}/{total}")
        logger.info(f"  - Overdue: {len(tasks)}")
        print(f"\n--- Email Preview for {person} ---")
        print(f"To: {contacts[person]}")
        print(f"Subject: {subject}")
        print(f"Stats: {completed}/{total} completed, {len(tasks)} overdue")
        continue

    success = send_email(contacts[person], subject, body_html)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if success:
        emails_sent += 1
        logger.info(
            f"Email sent to {person} ({contacts[person]}) - {completed}/{total} completed, {len(tasks)} overdue")
        with open("reminder_log.txt", "a") as f:
            f.write(
                f"[{timestamp}]SUCCESS - Email to {person} ({len(tasks)} overdue videos, {completed}/{total} completed)\n")
    else:
        emails_failed += 1
        logger.error(f"Failed to send email to {person}")
        with open("reminder_log.txt", "a") as f:
            f.write(f"[{timestamp}] FAILED - Email to {person}\n")

logger.info("=" * 50)
if DRY_RUN:
    logger.info("DRY RUN completed - no actual emails sent")
else:
    logger.info(f"Email run completed: {emails_sent} sent, {emails_failed} failed")
    print(f"\nReminder script completed: {emails_sent} sent, {emails_failed} failed")
