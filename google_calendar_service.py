import datetime
import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_calendar_service():
    creds = None
    if 'credentials' not in st.session_state:
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                    "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"]
                }
            },
            SCOPES
        )
        creds = flow.run_local_server(port=0)
        st.session_state['credentials'] = creds.to_json()
    else:
        creds = Credentials.from_authorized_user_info(st.session_state['credentials'], SCOPES)
    return build('calendar', 'v3', credentials=creds)

def add_events_to_calendar(plan):
    service = get_calendar_service()
    today = datetime.date.today()

    for day_plan in plan:
        event = {
            'summary': f"Study: {', '.join(day_plan['topics'])}",
            'start': {
                'dateTime': f"{today}T09:00:00",
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': f"{today}T12:00:00",
                'timeZone': 'Asia/Kolkata',
            },
        }
        service.events().insert(calendarId='primary', body=event).execute()
        today += datetime.timedelta(days=1)
