import streamlit as st
import os
import tempfile
import json
import PyPDF2
import docx
from dotenv import load_dotenv
import google.generativeai as genai
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import datetime as dt
import requests

# Load .env
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

    # Try to extract JSON
    try:
        plan_json = json.loads(plan_text)
    except Exception:
        import re
        m = re.search(r"\{.*\}", plan_text, re.DOTALL)
        if not m:
            st.error("Couldn't parse study plan from AI response.")
            return None
        plan_json = json.loads(m.group(0))
    return plan_json

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

# ------------------- Streamlit UI -------------------

st.set_page_config(page_title="AI Study Planner", layout="wide")
st.title("📘 AI Study Planner with Google Calendar Integration")

uploaded_file = st.file_uploader("Upload your study material (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"])
days = st.slider("How many days do you want the study plan for?", 3, 30, 7)

if uploaded_file and st.button("Generate Study Plan"):
    with st.spinner("Analyzing your file and generating a plan..."):
        text = extract_text(uploaded_file)
        plan = get_study_plan(text, days)
        if plan:
            st.session_state["plan"] = plan
            st.success("✅ Study plan generated successfully!")

if "plan" in st.session_state:
    plan = st.session_state["plan"]
    st.subheader(plan.get("title", "Your Study Plan"))
    st.write("### Topics")
    for t in plan.get("topics", []):
        with st.expander(t["name"]):
            st.markdown(f"**Summary:** {t['summary']}")
            st.markdown(f"**Estimated Hours:** {t['estimated_hours']}")
            st.markdown("**Resources:**")
            for r in t["resources"]:
                if "geeksforgeeks" in r.lower():
                    st.markdown(f"- 🔗 [GeeksforGeeks]({r})")
                else:
                    st.markdown(f"- 🔗 {r}")

    st.write("### Schedule")
    st.table(plan["schedule"])

    # Google Calendar integration
    st.divider()
    st.write("#### 🗓️ Add to Google Calendar")

    if "google_creds" not in st.session_state:
        client_id = st.secrets["GOOGLE_CLIENT_ID"]
        client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]

        # Google OAuth flow
        flow = Flow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["https://studyschedule1-zhc7eg7dgb49ygtbskorze.streamlit.app"]
                }
            },
            scopes=["https://www.googleapis.com/auth/calendar.events"],
            redirect_uri="https://studyschedule1-zhc7eg7dgb49ygtbskorze.streamlit.app"
        )

        auth_url, _ = flow.authorization_url(prompt="consent")
        st.markdown(f"[Click here to connect Google Calendar]({auth_url})")

        query_params = st.experimental_get_query_params()
        if "code" in query_params:
            code = query_params["code"][0]
            flow.fetch_token(code=code)
            creds = flow.credentials
            st.session_state["google_creds"] = json.loads(creds.to_json())
            st.experimental_rerun()
    else:
        if st.button("Add Plan to Google Calendar"):
            with st.spinner("Adding events to your calendar..."):
                links = add_to_calendar(plan, st.session_state["google_creds"])
                st.success(f"✅ Added {len(links)} events to your Google Calendar!")
                for l in links:
                    st.markdown(f"- [View Event]({l})")
