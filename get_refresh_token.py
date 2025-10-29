# get_refresh_token.py
"""
Run this locally (desktop) to obtain a refresh_token.
Usage:
  1. Put downloaded credentials.json (Desktop OAuth client) next to this script.
  2. python get_refresh_token.py
  3. Copy the printed JSON: you need client_id, client_secret, and refresh_token.
"""
from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)
print("\n=== Save these values securely (do NOT commit) ===\n")
print(creds.to_json())  # includes access_token and refresh_token (if granted)
# optionally write to token.json locally for inspection
with open("token.json", "w") as f:
    f.write(creds.to_json())
print("\nWrote token.json (local). From the printed JSON copy refresh_token, client_id and client_secret into Streamlit Secrets.")
