import subprocess, json, re, shutil, csv
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.utils import rowcol_to_a1
from gspread_formatting import DataValidationRule, BooleanCondition
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

required_vars = ["PLAYLIST_URL", "START_DATE", "PARTICIPANTS", "SHEET_NAME", "SHARE_EMAIL"]
missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

playlist_url = os.getenv("PLAYLIST_URL")
try:
    start_date = datetime.strptime(os.getenv("START_DATE"), "%Y-%m-%d")
except ValueError as e:
    logger.error(f"Invalid START_DATE format. Use YYYY-MM-DD format (e.g., 2025-11-10): {e}")
    raise
participants = os.getenv("PARTICIPANTS").split(",")
sheet_name = os.getenv("SHEET_NAME")
share_email = os.getenv("SHARE_EMAIL")
DRY_RUN = os.getenv("DRY_RUN", "false").lower()=="true"

if DRY_RUN:
    logger.info("DRY RUN MODE - No actual changes will be made to Google Sheets")


def backup_credentials():
    """Backup credentials.json - keeps only the most recent backup"""
    if os.path.exists("credentials.json"):
        for old_backup in os.listdir("."): # Added a Delete backup routine
            if old_backup.startswith("credentials_backup_") and old_backup.endswith(".json"):
                try:
                    os.remove(old_backup)
                except Exception:
                    pass

        backup_name = f"credentials_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        shutil.copy("credentials.json", backup_name)
        logger.info(f"Credentials backed up to {backup_name}")


def clean_title(title):
    # Title Cleaning - Emojis can break the Google Sheets
    cleaned = re.sub(r'[^\w\s\-\(\).,!?]', '', title).strip()
    return cleaned if cleaned else "Untitled Video"


def is_valid_youtube_url(url):
    pattern = r'^https://www\.youtube\.com/watch\?v=[\w-]+$'
    return bool(re.match(pattern, url))


def export_backup(data, filename="tracker_backup"):
    backup_dir = "backups" # Created a backup routine for easier debugging
    os.makedirs(backup_dir, exist_ok=True)

    # Delete old backups with same filename prefix
    for old_file in os.listdir(backup_dir):
        if old_file.startswith(filename + "_"):
            try:
                os.remove(os.path.join(backup_dir, old_file))
            except Exception:
                pass

    backup_file = f"{backup_dir}/{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(backup_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(data)

    logger.info(f"Backup saved to {backup_file}")


backup_credentials()

logger.info(f"Fetching playlist from: {playlist_url}")
cmd = ["yt-dlp", "-J", "--flat-playlist", playlist_url]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode!=0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")

    data_json = json.loads(result.stdout)

    if not data_json.get("entries"):
        raise ValueError("Playlist is empty or couldn't be fetched")

    logger.info(f"Successfully fetched {len(data_json['entries'])} videos")

except subprocess.TimeoutExpired:
    logger.error("yt-dlp timed out after 60 seconds")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Failed to parse yt-dlp output: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error fetching playlist: {e}")
    raise

videos = []
skipped_count = 0

for entry in data_json["entries"]:
    title = clean_title(entry.get("title", ""))
    url = f'https://www.youtube.com/watch?v={entry["id"]}'

    if is_valid_youtube_url(url):
        videos.append((title, url))
    else:
        logger.warning(f"Skipping invalid video URL: {url}")
        skipped_count += 1

if skipped_count > 0:
    logger.warning(f"Skipped {skipped_count} videos with invalid URLs")

logger.info(f"Processed {len(videos)} valid videos")

# Date and Schedule
data = []
day_counter, video_index = 1, 0
current_date = start_date

while video_index < len(videos):
    if current_date.weekday() >= 5:  # Sat=5, Sun=6
        row = {
            "Day":"Weekend",
            "Date":current_date.strftime("%Y-%m-%d"),
            "Video Title":"Revision / Code / Notes",
            "Video URL":""
        }
        for p in participants:
            row[p] = ""
        data.append(row)
        current_date += timedelta(days=1)
        continue

    for i in range(3):     # 3 Videos per day, can be changed as required
        if video_index < len(videos):
            title, url = videos[video_index]
            row = {
                "Day":f"Day {day_counter}",
                "Date":current_date.strftime("%Y-%m-%d"),
                "Video Title":title,
                "Video URL":f'=HYPERLINK("{url}", "Link")'
            }
            for p in participants:
                row[p] = ""
            data.append(row)
            video_index += 1
    day_counter += 1
    current_date += timedelta(days=1)

df = pd.DataFrame(data)
completion_date = current_date - timedelta(days=1)
logger.info(f"Created schedule with {len(df)} rows spanning {day_counter - 1} working days")
logger.info(f"Start: {start_date.strftime('%Y-%m-%d')}, End: {completion_date.strftime('%Y-%m-%d')}")

export_backup([df.columns.values.tolist()] + df.values.tolist(), "schedule_data")

if DRY_RUN:
    logger.info("DRY RUN: Would create spreadsheet with following data:")
    print(df.head(10))
    logger.info(f"Total rows: {len(df)}")
    logger.info("Exiting without making changes to Google Sheets")
    exit(0)

# API Calls
logger.info("Connecting to Google Sheets...")
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

try:
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    logger.info("Successfully authenticated with Google")
except Exception as e:
    logger.error(f"Failed to authenticate with Google: {e}")
    raise

try:
    spreadsheet = client.open(sheet_name)
    logger.info(f"Opened existing spreadsheet: {sheet_name}")
except gspread.SpreadsheetNotFound:
    logger.info(f"Creating new spreadsheet: {sheet_name}")
    spreadsheet = client.create(sheet_name)

spreadsheet.share(share_email, perm_type="user", role="writer")
logger.info(f"Shared spreadsheet with {share_email}")

worksheet = spreadsheet.get_worksheet(0)
worksheet.update([df.columns.values.tolist()] + df.values.tolist(),
                 value_input_option='USER_ENTERED')
logger.info("Updated spreadsheet with schedule data")

# Excel Block TODO - Add further formatting
worksheet.freeze(rows=1)

fmt = {
    "backgroundColor":{"red":0.74, "green":0.86, "blue":0.95},  # light blue
    "textFormat":{"bold":True}
}
worksheet.format("1:1", fmt)

from gspread_formatting import set_data_validation_for_cell_range # Call Data Validation Library

for p in participants:
    if p in df.columns:
        col_idx = df.columns.get_loc(p)
        col_letter = chr(65 + col_idx)  # A Column

        try:
            rule = DataValidationRule(
                BooleanCondition('ONE_OF_LIST', ['done', 'skipped', 'in progress']), #Drop Down Validation
                showCustomUi=True
            )
            set_data_validation_for_cell_range(
                worksheet,
                f'{col_letter}2:{col_letter}{len(df) + 1}',
                rule
            )
            logger.info(f"Added dropdown validation for column {p}")
        except Exception as e:
            logger.warning(f"Could not add dropdown for {p}: {e}")

sheet_id = worksheet.id
n_rows = len(df) + 1
n_cols = len(df.columns)

requests = []
for p in participants:
    if p in df.columns:
        col_idx = df.columns.get_loc(p)  # 0-based
        top_left = rowcol_to_a1(2, col_idx + 1)

        requests.append({
            "addConditionalFormatRule":{
                "rule":{
                    "ranges":[{
                        "sheetId":sheet_id,
                        "startRowIndex":1,
                        "endRowIndex":n_rows,
                        "startColumnIndex":col_idx,
                        "endColumnIndex":col_idx + 1
                    }],
                    "booleanRule":{
                        "condition":{
                            "type":"CUSTOM_FORMULA",
                            "values":[{"userEnteredValue":f'=LOWER({top_left})="done"'}]
                        },
                        "format":{"backgroundColor":{"red":0.80, "green":0.94, "blue":0.80}}
                    }
                },
                "index":0
            }
        })

        requests.append({
            "addConditionalFormatRule":{
                "rule":{
                    "ranges":[{
                        "sheetId":sheet_id,
                        "startRowIndex":1,
                        "endRowIndex":n_rows,
                        "startColumnIndex":col_idx,
                        "endColumnIndex":col_idx + 1
                    }],
                    "booleanRule":{
                        "condition":{
                            "type":"CUSTOM_FORMULA",
                            "values":[{"userEnteredValue":f'=LEN(TRIM({top_left}))=0'}]
                        },
                        "format":{"backgroundColor":{"red":1.0, "green":0.84, "blue":0.84}}
                    }
                },
                "index":0
            }
        })

day_colors = [
    {"red":0.9, "green":0.95, "blue":1.0},  # Day 1: light blue
    {"red":0.9, "green":0.85, "blue":0.9},  # Day 2: light purple
    {"red":1.0, "green":0.95, "blue":0.9},  # Day 3: light orange
    {"red":1.0, "green":0.8, "blue":0.95},  # Day 4: light pink
    {"red":0.85, "green":0.8, "blue":0.9},  # Day 5: light lavender
]

for i, color in enumerate(day_colors, start=1):
    mod_val = i if i < 5 else 0  # Day 5 → MOD(...,5)=0
    formula = (
        f'=AND(ISNUMBER(VALUE(REGEXEXTRACT($A2,"[0-9]+"))),'
        f'MOD(VALUE(REGEXEXTRACT($A2,"[0-9]+")),5)={mod_val})'
    )
    requests.append({
        "addConditionalFormatRule":{
            "rule":{
                "ranges":[{
                    "sheetId":sheet_id,
                    "startRowIndex":1,
                    "endRowIndex":n_rows,
                    "startColumnIndex":0,
                    "endColumnIndex":4
                }],
                "booleanRule":{
                    "condition":{
                        "type":"CUSTOM_FORMULA",
                        "values":[{"userEnteredValue":formula}]
                    },
                    "format":{"backgroundColor":color}
                }
            },
            "index":0
        }
    })

# -Weekend = No Videos Planned
requests.append({
    "addConditionalFormatRule":{
        "rule":{
            "ranges":[{
                "sheetId":sheet_id,
                "startRowIndex":1,
                "endRowIndex":n_rows,
                "startColumnIndex":0,
                "endColumnIndex":n_cols  # all columns
            }],
            "booleanRule":{
                "condition":{
                    "type":"CUSTOM_FORMULA",
                    "values":[{"userEnteredValue":'=$A2="Weekend"'}]
                },
                "format":{
                    "backgroundColor":{"red":0.9, "green":0.9, "blue":0.9},  # gray
                    "textFormat":{"bold":True},
                }
            }
        },
        "index":0
    }
})

worksheet.spreadsheet.batch_update({"requests":requests})
logger.info("Applied all formatting rules")

logger.info("Tracker created successfully!")
print(f"\nTracker saved: {spreadsheet.url}")
print(f"Total videos: {len(videos)}")
print(f"Videos per weekday: 3")
print(f"Total working days needed: {day_counter - 1}")
print(f"Schedule start date: {start_date.strftime('%Y-%m-%d')} ({start_date.strftime('%B %d, %Y')})")
print(
    f"Estimated completion date: {(current_date - timedelta(days=1)).strftime('%Y-%m-%d')} ({(current_date - timedelta(days=1)).strftime('%B %d, %Y')})")
