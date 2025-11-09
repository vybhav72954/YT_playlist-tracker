# Youtube Playlist Tracker

Turn your favorite YouTube playlist into a Google Sheet for real-time tracking and collaboration with friends.
Each video is listed with a clickable link, and you and your friends can mark progress directly in the sheet.
- The script fetches all video titles from a YouTube playlist.
- Builds a study schedule (3 videos per weekday, weekends for review).
- Uploads the schedule to Google Sheets, so everyone marks their progress collaboratively.
- A weekly reminder email is sent to each participant if they fall behind.

This makes group study structured, accountable, and transparent.

[![image.png](https://i.postimg.cc/cHsnZqFc/image.png)](https://postimg.cc/bGBJH5cG)

## Setup

1. Install requirements:

```pip install -r requirements.txt```

2. Enable Google Sheets API and Google Drive API in Google Cloud.
Download your service account key as `credentials.json` and place it in the project `src` folder.
   - Visit → https://console.developers.google.com/
   - Create project → Enable Google Sheets API + Google Drive API 
   - Create → Service Account → Create JSON Key
3. *First time using Google Console?* I have added more details [here](API-SETUP.md)!

4. Create a ```.env``` file in the project root. Refer to the [Sample Environment file](env.sample)

_You must use an App Password, not your real Gmail password:_
_https://myaccount.google.com/apppasswords_

6. Run
```bash
python main.py
```

This will:
- Fetch the playlist videos
- Push them to Google Sheets with clickable links
- Share the sheet with you for collaboration
- Apply simple conditional formatting (✅ done / ❌ pending)

7. Send Email Reminders
```bash
python src/email_reminder.py
```

**Important** - I have enabled debugging flags.
```bash
set DRY_RUN=true\fales
set EMAIL_ENABLED=true\false
```

### Automating Weekly Email at Midnight (Windows)

- Open Task Scheduler

  - Click Create Task…

- General Tab

  - Name: Email Reminder

  - Select Run whether user is logged on or not

  - Check Run with highest privileges

- Triggers Tab

  - New → Daily → Time: 12:00 AM

- Actions Tab

  - Action: Start a Program

  - Program/script:
     ```bash
     C:\Users\..\..\Youtube_Tracker\venv\Scripts\python.exe
     ```
  - Add Arguments:
     ```bash
     C:\Users\..\..\Youtube_Tracker\src\email_reminder.py
     ```
  - Start IN
     ```bash
     C:\Users\..\..\Youtube_Tracker\src
     ```

- Settings Tab

  - ✅ Allow task to be run on demand

  - ✅ Run task as soon as possible after a missed start

  - Change: If the task is already running → Run a new instance

- Click OK → enter your Windows password if prompted.

## Future Additions

- [ ] Extension for ease of use

- [x] Nudges/Notifications when schedule not met 

- [ ] Open to hear your feedback :)
