## Google API Setup
1. Create a Project in Google Cloud

- Go to Google Cloud Console .
- Click the project dropdown → New Project → give it a name (e.g., YouTubeTracker).

2. Enable APIs

- In your new project, go to APIs & Services → Library.
- Search and enable:
  - Google Sheets API 
  - Google Drive API

3. Create a Service Account

- Go to APIs & Services → Credentials.
- Click Create Credentials → Service Account. 
- Give it a name (e.g., Sheets Service Account) → Create.

4. Create a JSON Key

- Open your new service account.
- Go to Keys → Add Key → Create New Key → JSON.
- Download the file → rename it credentials.json.
- Place it in your project root (same folder as main.py).

- ⚠️ Add credentials.json to .gitignore to keep it private. **Never commit it to GitHub**.

5. Share Your Google Sheet

- The service account has an email like:
```your-service@your-project.iam.gserviceaccount.com```
- Share your target Google Sheet with this email (just like sharing with a friend). 
- Give it Editor access.
