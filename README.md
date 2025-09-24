# Youtube Playlist Tracker

Turn your favorite YouTube playlist into a Google Sheet for real-time tracking and collaboration with friends.
Each video is listed with a clickable link, and you and your friends can mark progress directly in the sheet.

## Setup

1. Install requirements:

```pip install -r requirements.txt```

2. Enable Google Sheets API and Google Drive API in Google Cloud.
Download your service account key as credentials.json and place it in the project root.

3. Create a ```.env``` file in the project root:

```bash
PLAYLIST_URL=https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID
START_DATE=2025-09-29
PARTICIPANTS=Alice,Bob,Charlie
SHEET_NAME=MyPlaylistTracker
SHARE_EMAIL=your_email@gmail.com
```
4. Run
```bash
python main.py
```

This will:
- Fetch the playlist videos
- Push them to Google Sheets with clickable links
- Share the sheet with you for collaboration
- Apply simple conditional formatting (✅ done / ❌ pending)

## Future Additions

 - Extension for ease of use
 - Nudges/Notifications when schedule not met
 - Open to hear your feedback :)
