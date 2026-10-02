# Niyature Technologies - Seminar Attendance

Streamlit seminar attendance application using GitHub as persistent CSV storage.

## Features
- Public seminar attendance URL
- Bulk attendance from one device
- Duplicate roll-number protection
- CSV storage in GitHub
- Conflict retry for simultaneous submissions
- Admin login
- Seminar URL generator
- QR code generation
- Attendance CSV viewer/download
- No database

## Streamlit Secrets
Add these in Streamlit Cloud:

```toml
GITHUB_OWNER = "Niyaturetech"
GITHUB_REPO = "student_attendance"
GITHUB_BRANCH = "main"
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN"
ATTENDANCE_DIR = "attendance"
ADMIN_PASSWORD = "YOUR_ADMIN_PASSWORD"
APP_URL = "https://YOUR-APP-NAME.streamlit.app"
```

Never commit the real token.

## Admin
Open:

`https://YOUR-APP-NAME.streamlit.app/?admin=1`

## Student URL
Example:

`https://YOUR-APP-NAME.streamlit.app/?seminar=Big%20Data%20AI&date=2026-10-05&college=ABC%20College`

## Deployment
1. Upload/push the project to `Niyaturetech/student_attendance`.
2. Deploy `app.py` on Streamlit Cloud.
3. Branch: `main`.
4. Configure Secrets.
5. Redeploy.
6. Open `?admin=1`.
7. Generate the seminar link/QR.
8. Share it with students.

Attendance files are automatically created under `attendance/`, for example:
`attendance/2026-10-05_ABC_College.csv`
