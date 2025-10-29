import streamlit as st
from gemini_service import extract_pdf_text, generate_study_plan
from google_calendar_service import add_events_to_calendar
import json

st.set_page_config(page_title="AI Study Planner", page_icon="📘")

st.title("📘 AI Study Planner with Google Calendar")

uploaded_file = st.file_uploader("Upload your study material (PDF)", type=["pdf"])
duration = st.number_input("Duration (days)", min_value=1, max_value=90, value=7)
hours_per_day = st.number_input("Hours per day", min_value=1, max_value=12, value=3)

if uploaded_file and st.button("Generate Study Plan"):
    with st.spinner("Analyzing content using Gemini..."):
        pdf_text = extract_pdf_text(uploaded_file)
        plan_text = generate_study_plan(pdf_text, duration, hours_per_day)
        st.session_state["plan_text"] = plan_text

    st.success("✅ Study plan generated successfully!")
    st.text_area("Generated Plan", plan_text, height=300)

if "plan_text" in st.session_state and st.button("Add to Google Calendar"):
    try:
        plan_json = json.loads(st.session_state["plan_text"])
        add_events_to_calendar(plan_json)
        st.success("✅ Added to Google Calendar successfully!")
    except Exception as e:
        st.error(f"Google authentication error: {e}")
