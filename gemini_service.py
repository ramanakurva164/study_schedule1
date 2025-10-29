import google.generativeai as genai
from dotenv import load_dotenv
import os
import PyPDF2
import textwrap

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_pdf_text(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def generate_study_plan(pdf_text, duration, hours_per_day):
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = f"""
    Analyze the following study material and generate a detailed study plan:
    - Study duration: {duration} days
    - Study hours per day: {hours_per_day}

    Content:
    {textwrap.shorten(pdf_text, width=5000)}

    Output the study timetable in JSON with the structure:
    [
      {{
        "day": "Day 1",
        "topics": ["Topic 1", "Topic 2"],
        "hours": 3
      }},
      ...
    ]
    """
    response = model.generate_content(prompt)
    return response.text
