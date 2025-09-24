import subprocess, json
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.utils import rowcol_to_a1
from dotenv import load_dotenv
import os

# Environment Configuration
load_dotenv()

playlist_url = os.getenv("PLAYLIST_URL")
start_date = datetime.fromisoformat(os.getenv("START_DATE"))
participants = os.getenv("PARTICIPANTS").split(",")
sheet_name = os.getenv("SHEET_NAME")
share_email = os.getenv("SHARE_EMAIL")

# Fetch playlist
cmd = ["yt-dlp", "-J", "--flat-playlist", playlist_url]
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode != 0:
    raise RuntimeError(f"yt-dlp failed: {result.stderr}")

data_json = json.loads(result.stdout)

videos = [(entry["title"], f'https://www.youtube.com/watch?v={entry["id"]}')
          for entry in data_json["entries"]]

# Date and Schedule
data = []
day_counter, video_index = 1, 0
current_date = start_date

while video_index < len(videos):
    # Weekend for break and revision
    if current_date.weekday() >= 5:  # Sat=5, Sun=6
        row = {
            "Day": "Weekend",
            "Date": current_date.strftime("%Y-%m-%d"),
            "Video Title": "Revision / Code / Notes",
            "Video URL": ""
        }
        for p in participants:
            row[p] = ""
        data.append(row)
        current_date += timedelta(days=1)
        continue

    # 3 Videos per day
    for i in range(3):
        if video_index < len(videos):
            title, url = videos[video_index]
            row = {
                "Day": f"Day {day_counter}",
                "Date": current_date.strftime("%Y-%m-%d"),
                "Video Title": title,
                "Video URL": f'=HYPERLINK("{url}", "Link")'
            }
            for p in participants:
                row[p] = ""
            data.append(row)
            video_index += 1
    day_counter += 1
    current_date += timedelta(days=1)


df = pd.DataFrame(data)

# Google API!
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

spreadsheet = client.open(sheet_name)
spreadsheet.share(share_email, perm_type="user", role="writer")  # replace with your Gmail

worksheet = spreadsheet.get_worksheet(0)


worksheet.update([df.columns.values.tolist()] + df.values.tolist(),
                 value_input_option='USER_ENTERED')
# Formatting Block

# --- Freeze header row
worksheet.freeze(rows=1)

# --- Bold + background color for headers
fmt = {
    "backgroundColor": {"red": 0.74, "green": 0.86, "blue": 0.95},  # light blue
    "textFormat": {"bold": True}
}
worksheet.format("1:1", fmt)

sheet_id = worksheet.id
n_rows = len(df) + 1
n_cols = len(df.columns)

requests = []
for p in participants:
    if p in df.columns:
        col_idx = df.columns.get_loc(p)  # 0-based
        top_left = rowcol_to_a1(2, col_idx + 1)

        # --- "done" conditional formatting
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": n_rows,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": f'=LOWER({top_left})="done"'}]
                        },
                        "format": {"backgroundColor": {"red": 0.80, "green": 0.94, "blue": 0.80}}
                    }
                },
                "index": 0
            }
        })

        # --- red conditional formatting
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": n_rows,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": f'=LEN(TRIM({top_left}))=0'}]
                        },
                        "format": {"backgroundColor": {"red": 1.0, "green": 0.84, "blue": 0.84}}
                    }
                },
                "index": 0
            }
        })

# --- Colour Bands (repeated every week)
day_colors = [
    {"red": 0.9, "green": 0.95, "blue": 1.0},   # Day 1: light blue
    {"red": 0.9, "green": 0.85, "blue": 0.9},    # Day 2: light green
    {"red": 1.0, "green": 0.95, "blue": 0.9},   # Day 3: light orange
    {"red": 1.0, "green": 0.8, "blue": 0.95},   # Day 4: light pink
    {"red": 0.85, "green": 0.8, "blue": 0.9},   # Day 5: light purple
]

for i, color in enumerate(day_colors, start=1):
    mod_val = i if i < 5 else 0  # Day 5 → MOD(...,5)=0
    formula = (
        f'=AND(ISNUMBER(VALUE(REGEXEXTRACT($A2,"[0-9]+"))),'
        f'MOD(VALUE(REGEXEXTRACT($A2,"[0-9]+")),5)={mod_val})'
    )
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": n_rows,
                    "startColumnIndex": 0,
                    "endColumnIndex": 4
                }],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": formula}]
                    },
                    "format": {"backgroundColor": color}
                }
            },
            "index": 0
        }
    })

# --- Weekend rows
requests.append({
    "addConditionalFormatRule": {
        "rule": {
            "ranges": [{
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": n_rows,
                "startColumnIndex": 0,
                "endColumnIndex": n_cols   # all columns
            }],
            "booleanRule": {
                "condition": {
                    "type": "CUSTOM_FORMULA",
                    "values": [{"userEnteredValue": '=$A2="Weekend"'}]
                },
                "format": {
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},  # gray
                    "textFormat": {"bold": True},
                }
            }
        },
        "index": 0
    }
})

worksheet.spreadsheet.batch_update({"requests": requests})

print("Tracker saved")
