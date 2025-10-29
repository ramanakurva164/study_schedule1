# streamlit_app.py
import streamlit as st
from datetime import date, timedelta
import io
import json

from mcp_connector import creds_from_refresh_token, list_user_calendars, create_study_events

st.set_page_config(page_title="AI Study Scheduler", layout="centered")

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

st.title("AI Study Scheduler — Streamlit + Google Calendar")

# ---------- Load Google secrets ----------
if "google" not in st.secrets:
    st.warning("Google OAuth secrets not found in Streamlit Secrets. Add client_id, client_secret, refresh_token under [google].")
    st.stop()

google = st.secrets["google"]
client_id = google.get("client_id")
client_secret = google.get("client_secret")
refresh_token = google.get("refresh_token")

if not all([client_id, client_secret, refresh_token]):
    st.error("Please set client_id, client_secret, and refresh_token in Streamlit Secrets.")
    st.stop()

# ---------- Input UI ----------
st.markdown("## Upload study material (PDF) or paste topics manually")
uploaded = st.file_uploader("Upload a PDF (optional)", type=["pdf"])
manual_topics = st.text_area("Or paste topics (one per line)", height=120)

start_date = st.date_input("Start date", value=date.today())
days = st.number_input("Number of days to plan", min_value=1, value=7)
hours_per_day = st.number_input("Hours per day (used to bound schedule)", min_value=1.0, value=2.0, step=0.5)
default_start_hour = st.number_input("Default start hour (24h)", min_value=0, max_value=23, value=18)

# ---------- Parse / Plan generation (placeholder) ----------
def extract_topics_from_pdf(file_bytes):
    # Placeholder: real implementation should parse PDF & pick topics via LLM / LangChain
    # For now we'll return dummy topics.
    # You can replace this with your existing parser code that returns list of topics with weights
    text = "Extracted topics placeholder"
    return ["Topic A", "Topic B", "Topic C", "Topic D", "Topic E"]

def build_plan(topics, days, hours_per_day):
    # Naive distribution: give each topic equal hours across days until filled
    plan = []
    total_hours_available = days * hours_per_day
    per_topic_hours = max(0.5, total_hours_available / max(1, len(topics)))
    # allocate one topic per day if more topics than days, else multiple per day
    day = 1
    for i, t in enumerate(topics):
        plan.append({
            "day": day,
            "topic": t,
            "hours": round(min(per_topic_hours, hours_per_day), 2),
            "focus": "Study and practice",
            "resources": []
        })
        day += 1
        if day > days:
            day = 1
    return plan

topics = []
if uploaded:
    try:
        bytes_data = uploaded.read()
        topics = extract_topics_from_pdf(bytes_data)
        st.success(f"Extracted {len(topics)} topics from uploaded PDF (placeholder).")
    except Exception as e:
        st.error(f"PDF parsing error: {e}")
elif manual_topics.strip():
    topics = [line.strip() for line in manual_topics.splitlines() if line.strip()]

if not topics:
    st.info("Provide a PDF or paste topics to generate a plan.")
    st.stop()

if st.button("Generate Plan"):
    plan_rows = build_plan(topics, int(days), float(hours_per_day))
    st.subheader("Generated plan (sample)")
    st.table(plan_rows)
    st.session_state["plan_rows"] = plan_rows

# ---------- Calendar integration ----------
st.markdown("---")
st.subheader("Google Calendar Sync")

# Get credentials from refresh token
try:
    creds = creds_from_refresh_token(client_id, client_secret, refresh_token)
except Exception as e:
    st.error(f"Failed to build credentials from refresh token: {e}")
    st.stop()

# List calendars
try:
    cals = list_user_calendars(creds)
    cal_map = {f'{c["summary"]} ({c["id"]})': c["id"] for c in cals if c.get("accessRole") in ("owner", "writer")}
    selected_calendar = st.selectbox("Choose calendar to write events to", options=list(cal_map.keys()))
    calendar_id = cal_map[selected_calendar]
except Exception as e:
    st.error(f"Failed to list calendars: {e}")
    st.stop()

if "plan_rows" not in st.session_state:
    st.info("Generate a plan first.")
    st.stop()

if st.button("Push plan to Google Calendar"):
    plan_rows = st.session_state["plan_rows"]
    # default start date is start_date
    created = create_study_events(plan_rows, start_date, creds, calendar_id=calendar_id, default_start_hour=int(default_start_hour))
    st.success("Push finished. Results:")
    st.write(created)
