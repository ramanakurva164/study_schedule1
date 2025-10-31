import streamlit as st
import os, tempfile, json, re, datetime as dt
import PyPDF2, docx
import google.generativeai as genai
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# ------------------- SESSION INITIALIZATION -------------------
for key in ["plan", "google_creds", "google_auth_done", "created_event_ids", "step"]:
    if key not in st.session_state:
        if key == "google_auth_done":
            st.session_state[key] = False
        elif key == "created_event_ids":
            st.session_state[key] = []
        elif key == "step":
            st.session_state[key] = "connect"  # connect -> upload -> generate
        else:
            st.session_state[key] = None

# ------------------- CONFIG -------------------
st.set_page_config(page_title="AI Study Planner", layout="wide")
st.title("📘 AI Study Planner")

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ------------------- HELPERS -------------------
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


def get_study_plan(text, days=7, start_date=None):
    if not start_date:
        start_date = dt.date.today()
    
    # Generate date list
    date_list = [(start_date + dt.timedelta(days=i)).isoformat() for i in range(days)]
    
    prompt = f"""
    You are an AI Study Planner. Your goal is to create a {days}-day structured study plan starting from {start_date}.
    Use these exact dates: {date_list}
    
    The plan should be based on the following study material:
    {text[:8000]}
    
    For each day, assign a relevant topic, estimated duration (in minutes), a clear objective, 
    and 3–5 high-quality **resource links** from reliable sources like:
    - GeeksforGeeks
    - W3Schools
    - TutorialsPoint
    - Official documentation pages
    - FreeCodeCamp
    - Coursera (if relevant)

    🔹 Format the output strictly as JSON:
    {{
      "schedule": [
        {{
          "date": "{date_list[0]}",
          "topic": "Introduction to Machine Learning",
          "duration_minutes": 90,
          "objective": "Understand supervised and unsupervised learning",
          "resources": [
              "https://www.geeksforgeeks.org/machine-learning/",
              "https://scikit-learn.org/stable/",
              "https://www.w3schools.com/python/python_ml_getting_started.asp"
          ]
        }}
      ]
    }}
    """
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    plan_text = response.text.strip()
    try:
        return json.loads(plan_text)
    except Exception:
        m = re.search(r"\{.*\}", plan_text, re.DOTALL)
        return json.loads(m.group(0)) if m else None

def add_to_calendar(plan, creds_dict, start_time=dt.time(9,0), timezone="Asia/Kolkata"):
    creds = Credentials.from_authorized_user_info(creds_dict)
    service = build("calendar", "v3", credentials=creds)

    created_ids = []
    for session in plan.get("schedule", []):
        # Combine user's preferred date and time
        date_obj = dt.datetime.strptime(session['date'], '%Y-%m-%d').date()
        start_dt = dt.datetime.combine(date_obj, start_time)
        end_dt = start_dt + dt.timedelta(minutes=session.get("duration_minutes", 60))

        event = {
            "summary": f"Study: {session['topic']}",
            "description": session.get("objective", ""),
            "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
        }

        e = service.events().insert(calendarId="primary", body=event).execute()
        created_ids.append(e.get("id"))
    
    return created_ids

def add_to_calendar(plan, creds_dict, start_time=dt.time(9,0), timezone="Asia/Kolkata"):
    creds = Credentials.from_authorized_user_info(creds_dict)
    service = build("calendar", "v3", credentials=creds)

    created_ids = []
    for session in plan.get("schedule", []):
        date_obj = dt.datetime.strptime(session['date'], '%Y-%m-%d').date()
        start_dt = dt.datetime.combine(date_obj, start_time)
        end_dt = start_dt + dt.timedelta(minutes=session.get("duration_minutes", 60))

        # Prepare event description with objective + resource links
        description = session.get("objective", "")
        if "resources" in session:
            description += "\n\n📚 **Resources:**\n"
            for link in session["resources"]:
                description += f"- {link}\n"

        event = {
            "summary": f"Study: {session['topic']}",
            "description": description.strip(),
            "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
        }

        e = service.events().insert(calendarId="primary", body=event).execute()
        created_ids.append(e.get("id"))
    
    return created_ids


# ------------------- MAIN APP FLOW -------------------

# STEP 1: GOOGLE CALENDAR CONNECTION
if st.session_state["step"] == "connect":
    st.info("🔐 **Step 1: Connect to Google Calendar**")
    st.write("To get started, please connect your Google Calendar account first.")
    
    # ------------------- GOOGLE OAUTH -------------------
    redirect_uri = "https://studyschedule.streamlit.app/"
    client_id = st.secrets["GOOGLE_CLIENT_ID"]
    client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]

    flow = Flow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        redirect_uri=redirect_uri,
    )

    params = st.query_params

    if not st.session_state.get("google_creds") and "code" not in params:
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline", include_granted_scopes="true")
        st.markdown(f"### [🔗 Connect Google Calendar]({auth_url})")
        st.write("Click the link above to authenticate with your Google account and grant calendar permissions.")

    elif "code" in params:
        try:
            code = params["code"]
            flow.fetch_token(code=code)
            creds = flow.credentials
            st.session_state["google_creds"] = json.loads(creds.to_json())
            st.session_state["google_auth_done"] = True
            st.session_state["step"] = "upload"
            st.query_params.clear()
            st.success("✅ Google Calendar connected successfully!")
            st.rerun()

        except Exception as e:
            st.error(f"OAuth Error: {e}")

    elif st.session_state.get("google_auth_done"):
        st.session_state["step"] = "upload"
        st.rerun()

# STEP 2: FILE UPLOAD AND SETTINGS
elif st.session_state["step"] == "upload":
    st.success("✅ Google Calendar Connected")
    st.info("📂 **Step 2: Upload Study Material and Configure Plan**")
    
    uploaded_file = st.file_uploader("📂 Upload your study material (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"])
    
    col1, col2 = st.columns(2)
    with col1:
        days = st.slider("📅 How many days do you want the study plan for?", 3, 30, 7)
    with col2:
        hours_per_day = st.slider("⏰ Study hours per day", 1.0, 8.0, 2.0, 0.5)

    if uploaded_file and st.button("✨ Generate Study Plan & Add to Calendar"):
        with st.spinner("Analyzing file and generating plan..."):
            text = extract_text(uploaded_file)
            plan = get_study_plan(text, days)
            if plan:
                st.session_state["plan"] = plan
                st.session_state["step"] = "display"
                
                # Automatically add to calendar
                with st.spinner("Adding events to your Google Calendar..."):
                    try:
                        event_ids = add_to_calendar(plan, st.session_state["google_creds"])
                        st.session_state["created_event_ids"] = event_ids
                        st.success(f"✅ Study plan generated and {len(event_ids)} events added to your calendar!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Calendar error: {e}")
            else:
                st.error("Failed to generate study plan. Please try again.")

# STEP 3: DISPLAY PLAN WITH DELETE OPTION
elif st.session_state["step"] == "display" and st.session_state["plan"]:
    plan = st.session_state["plan"]
    
    st.success("✅ Study Plan Generated & Added to Calendar")
    
    # Control buttons at top
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        if st.button("� Generate New Plan"):
            st.session_state["step"] = "upload"
            st.session_state["plan"] = None
            st.rerun()
    with col2:
        if st.button("❌ Delete All Calendar Events") and st.session_state["created_event_ids"]:
            with st.spinner("Deleting events from calendar..."):
                deleted = delete_all_events(st.session_state["created_event_ids"], st.session_state["google_creds"])
                st.session_state["created_event_ids"] = []
                st.success(f"🗑️ Deleted {deleted} events from your calendar")
                st.rerun()
    
    st.divider()
    
    # Display plan details
    st.subheader(plan.get("title", "📘 Your Study Plan"))
    
    if st.session_state["created_event_ids"]:
        st.info(f"📅 **{len(st.session_state['created_event_ids'])} events** are currently scheduled in your Google Calendar")
    
    st.write("### 📘 Topics Overview")
    for t in plan.get("topics", []):
        with st.expander(f"📚 {t['name']} ({t.get('estimated_hours', 'N/A')} hours)"):
            st.markdown(f"**Summary:** {t['summary']}")
            st.write("**Resources:**")
            for r in t.get("resources", []):
                if r.startswith("http"):
                    st.markdown(f"- 🔗 [{r}]({r})")
                else:
                    st.markdown(f"- 📖 {r}")

    st.divider()
    st.write("### 🗓️ Daily Schedule")

    for i, session in enumerate(plan.get("schedule", []), 1):
        st.markdown(f"### 📅 Day {i}: {session['topic']}")
        st.markdown(f"**Date:** {session['date']}")
        st.markdown(f"**Duration:** {session.get('duration_minutes', 60)} minutes")
        st.markdown(f"**Objective:** {session.get('objective', 'No objective provided')}")
    
        # Display resource links on webpage
        resources = session.get("resources", [])
        if resources:
            st.markdown("**🔗 Resources:**")
            for link in resources:
                if link.startswith("http"):
                    st.markdown(f"- [{link}]({link})")
                else:
                    st.markdown(f"- {link}")
    
        st.divider()
