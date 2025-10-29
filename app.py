import streamlit as st
import os
import tempfile
import json
import PyPDF2
import docx
import google.generativeai as genai
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import datetime as dt
import re

# ------------------- CONFIG -------------------
st.set_page_config(page_title="AI Study Planner", layout="wide")
st.title("📘 AI Study Planner with Google Calendar Integration")

# Load Gemini API Key
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ------------------- Helper Functions -------------------

def extract_text(file):
    suffix = file.name.split(".")[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name

    if suffix == "pdf":
        reader = PyPDF2.PdfReader(tmp_path)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif suffix in ["docx", "doc"]:
        doc = docx.Document(tmp_path)
        return "\n".join([p.text for p in doc.paragraphs])
    else:
        return file.read().decode("utf-8", errors="ignore")


def get_study_plan(text, days=7):
    prompt = f"""
    You are an AI tutor. Analyze the following study material and create a JSON plan:
    - Extract 5–7 key topics.
    - Estimate study time (hours) per topic.
    - Create a {days}-day study schedule with daily sessions.
    - For each topic, suggest 2–3 resources (GeeksforGeeks, official docs, YouTube tutorials).
    - Return JSON only, structured like this:
      {{
        "title": "...",
        "topics": [
          {{"name": "...", "summary": "...", "estimated_hours": 3, "resources": ["...","..."]}}
        ],
        "schedule": [
          {{"date": "2025-11-01", "topic": "...", "duration_minutes": 60, "objective": "..."}}
        ]
      }}
    Study material:
    {text[:8000]}
    """

    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    plan_text = response.text.strip()

    # Extract JSON safely
    try:
        return json.loads(plan_text)
    except Exception:
        m = re.search(r"\{.*\}", plan_text, re.DOTALL)
        if not m:
            st.error("❌ Couldn't parse study plan from AI response.")
            return None
        return json.loads(m.group(0))


def add_to_calendar(plan, creds_dict):
    creds = Credentials.from_authorized_user_info(creds_dict)
    service = build("calendar", "v3", credentials=creds)

    created = []
    for session in plan.get("schedule", []):
        start_dt = dt.datetime.fromisoformat(f"{session['date']}T09:00:00")
        end_dt = start_dt + dt.timedelta(minutes=session.get("duration_minutes", 60))

        event = {
            "summary": f"Study: {session['topic']}",
            "description": session.get("objective", ""),
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Kolkata"},
        }

        e = service.events().insert(calendarId="primary", body=event).execute()
        created.append(e.get("htmlLink"))
    return created

# ------------------- MAIN APP -------------------

uploaded_file = st.file_uploader(
    "📂 Upload your study material (PDF, DOCX, or TXT)",
    type=["pdf", "docx", "txt"]
)
days = st.slider("📅 How many days do you want the study plan for?", 3, 30, 7)

if uploaded_file and st.button("✨ Generate Study Plan"):
    with st.spinner("Analyzing file and generating plan..."):
        text = extract_text(uploaded_file)
        plan = get_study_plan(text, days)
        if plan:
            st.session_state["plan"] = plan
            st.success("✅ Study plan generated successfully!")

# ------------------- DISPLAY PLAN -------------------

if "plan" in st.session_state:
    plan = st.session_state["plan"]
    st.subheader(plan.get("title", "Your Study Plan"))

    st.write("### 📘 Topics")
    for t in plan.get("topics", []):
        with st.expander(t["name"]):
            st.markdown(f"**Summary:** {t['summary']}")
            st.markdown(f"**Estimated Hours:** {t['estimated_hours']}")
            st.markdown("**Resources:**")
            for r in t["resources"]:
                st.markdown(f"- 🔗 [{r}]({r})")

    st.divider()
    st.write("### 🗓️ Add to Google Calendar")

    # ------------------- GOOGLE CALENDAR -------------------
    redirect_uri = "https://studyschedule1-zhc7eg7dgb49ygtbskorze.streamlit.app/"

    if "google_creds" not in st.session_state:
        client_id = st.secrets["GOOGLE_CLIENT_ID"]
        client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]

        flow = Flow.from_client_config(
            {
                "web": {  # ✅ Important: Use web, not installed
                    "client_id": client_id,
                    "project_id": "study-schedule-app",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_secret": client_secret,
                    "redirect_uris": [redirect_uri],
                    "javascript_origins": [redirect_uri],
                }
            },
            scopes=["https://www.googleapis.com/auth/calendar.events"],
        )
        flow.redirect_uri = redirect_uri

        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline", include_granted_scopes="true")
        st.markdown(f"[🔗 Connect your Google Calendar]({auth_url})")

        # Handle redirect with `code`
        code = st.query_params.get("code")
        if code:
            try:
                flow.fetch_token(code=code)
                creds = flow.credentials
                st.session_state["google_creds"] = json.loads(creds.to_json())
                st.success("✅ Google Calendar connected successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ OAuth Error: {e}")

    else:
        if st.button("➕ Add Plan to Google Calendar"):
            with st.spinner("Adding events to your calendar..."):
                try:
                    links = add_to_calendar(plan, st.session_state["google_creds"])
                    st.success(f"✅ Added {len(links)} events to your Google Calendar!")
                    for l in links:
                        st.markdown(f"- [View Event]({l})")
                except Exception as e:
                    st.error(f"❌ Calendar error: {e}")
