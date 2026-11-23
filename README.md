# LabLink — Smart College Laboratory Resource Platform

LabLink is a hackathon-ready Flask + SQLite web application for discovering shared campus laboratory resources, submitting project access requests, reviewing requests as faculty, and booking equipment slots with conflict checks.

## Features

- Student and faculty demo sign-in
- Search/filter by equipment name, department and category; availability-only filter
- Equipment detail/specifications and current bookings
- Time-slot booking with overlapping-booking prevention
- Project access requests with deadline and purpose validation
- Faculty approval/rejection dashboard
- Project-keyword recommendations with live availability checks
- Optional Gemini API integration on the server; keyword-based fallback works without an API key
- Responsive UI, accessible labels, keyboard-operable controls, status messages and empty states

## Requirements

- Python 3.10+
- pip
- Optional: Gemini API key

## Run locally (Windows PowerShell)

1. Extract the ZIP and open PowerShell in the `LabLink` folder.
2. Create a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` in place of `python` in the commands below.

3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Set a development secret (recommended):

   ```powershell
   $env:SECRET_KEY = "replace-this-with-a-long-random-secret"
   ```

5. Optional Gemini configuration:

   ```powershell
   $env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
   ```

   The key is read only by the Flask backend. Never place it in `static/app.js`, HTML, GitHub, or a public repository. If omitted or the API call fails, LabLink uses its built-in fallback recommender.

6. Start the app:

   ```powershell
   python app.py
   ```

7. Open **http://127.0.0.1:5000** in your browser.

The SQLite database and realistic sample records are created automatically on first run. To reset demo data, stop the server and delete `lablink.db`; it will be recreated next time.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Student | `student@lablink.edu` | `student123` |
| Faculty | `faculty@lablink.edu` | `faculty123` |
| Student (Electronics) | `diya@lablink.edu` | `student123` |

These are demo-only credentials. Change them and add stronger account management before any real deployment.

## Test the main flows

1. Sign in as the student.
2. Search for `Jetson`, select a department/category, and open **View details**.
3. Choose a future start and end time (maximum four hours) and book it.
4. Submit a project access request with a future deadline and a purpose of at least 10 characters.
5. Click **Find AI recommendations** after entering a project name and purpose. It works without Gemini.
6. Sign out and sign in as faculty.
7. Approve or reject the pending student request.
8. Sign back in as the student and verify the request status.
9. Try to book the same fully occupied time slot again. LabLink returns a conflict response and alternative time/equipment suggestions.

## Deploy to Google Cloud Run

Cloud Run containers have an ephemeral writable filesystem by default. For a hackathon demo, SQLite is acceptable for a single instance, but its data may not persist across instance replacement and is not a production multi-instance database. For persistent or concurrent production use, replace SQLite with Cloud SQL (PostgreSQL).

1. Install and authenticate the Google Cloud CLI; select your project and enable Cloud Run and Cloud Build APIs.
2. From this folder, build and deploy:

   ```bash
   gcloud run deploy lablink \
     --source . \
     --region asia-south1 \
     --allow-unauthenticated \
     --set-env-vars SECRET_KEY=replace-with-a-long-random-secret
   ```

3. To configure Gemini securely, use Secret Manager and attach the secret as an environment variable. Example after creating a secret named `gemini-api-key` and granting the Cloud Run service identity access:

   ```bash
   gcloud run services update lablink \
     --region asia-south1 \
     --update-secrets GEMINI_API_KEY=gemini-api-key:latest
   ```

4. For production, also configure a persistent database, stronger authentication, CSRF protection, rate limiting, and role administration.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | Yes for deployment | Flask session signing secret |
| `GEMINI_API_KEY` | No | Optional Gemini API key, used only by backend |
| `DATABASE_PATH` | No | SQLite database path |
| `PORT` | No | Server port (Cloud Run provides it) |
| `FLASK_DEBUG` | No | Set to `1` only for local debugging |

## Architecture

- `app.py`: Flask routes, validation, SQLite queries, booking checks and recommender
- `templates/index.html`: single-page application shell
- `static/styles.css`: responsive design
- `static/app.js`: browser interactions and API calls
- `requirements.txt`: minimal Python dependency
- `Dockerfile`: Cloud Run container definition

## Important scope notes

This is a functional hackathon prototype, not a production university identity or access-control system. Demo passwords are intentionally simple. Faculty approval changes request status; a confirmed equipment booking is a separate action. Before real campus use, add institutional SSO, CSRF protection, audit logs, database migrations, persistent managed storage and stronger authorization policies.
