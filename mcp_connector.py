# mcp_connector.py
import json
import pytz
from datetime import datetime, timedelta, time as dt_time
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TIMEZONE = "Asia/Kolkata"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def creds_from_refresh_token(client_id, client_secret, refresh_token):
    """
    Build google.oauth2.credentials.Credentials using the refresh token (server-side).
    """
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )
    # Refresh once to obtain access_token
    request = Request()
    creds.refresh(request)
    return creds

def list_user_calendars(creds):
    """
    Return list of calendars (id, summary, primary, accessRole).
    """
    service = build("calendar", "v3", credentials=creds)
    calendars_result = service.calendarList().list().execute()
    calendars = calendars_result.get('items', [])
    # Return calendars where you can write
    return [{"id": c["id"], "summary": c.get("summary", c["id"]), "primary": c.get("primary", False), "accessRole": c.get("accessRole")} for c in calendars]

def create_study_events(plan_rows, start_date, creds, calendar_id="primary", default_start_hour=18, note=""):
    """
    plan_rows: list of dicts: {"day":1,"topic":"X","hours":2,"focus":"...","resources":[...]}
    start_date: datetime.date
    creds: google credentials
    Returns list of created event IDs (or errors logged).
    """
    service = build("calendar", "v3", credentials=creds)
    tz = pytz.timezone(TIMEZONE)
    created_ids = []

    for row in plan_rows:
        try:
            day_index = int(row.get("day", 1))
            event_date = start_date + timedelta(days=day_index - 1)
            start_dt = datetime.combine(event_date, dt_time(hour=int(default_start_hour), minute=0))
            start_dt = tz.localize(start_dt)
            hours = float(row.get("hours", 1))
            end_dt = start_dt + timedelta(hours=hours)

            description_lines = []
            if row.get("focus"):
                description_lines.append(f"Focus: {row.get('focus')}")
            if row.get("resources"):
                description_lines.append("\nResources:")
                for r in row.get("resources", []):
                    description_lines.append(f"- {r}")
            if note:
                description_lines.append(f"\nNote: {note}")

            event = {
                "summary": f"Study: {row.get('topic', 'Topic')}",
                "description": "\n".join(description_lines),
                "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
            }
            created = service.events().insert(calendarId=calendar_id, body=event).execute()
            created_ids.append(created.get("id"))
        except Exception as e:
            # Collect error and continue
            created_ids.append({"error": str(e), "row": row})
            continue

    return created_ids
