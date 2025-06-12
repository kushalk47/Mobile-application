# app/routes/patient_routes.py
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from bson import ObjectId
from datetime import datetime
import logging
import os
from pathlib import Path
import google.generativeai as genai  # Gemini API
from typing import Dict, Any
import re  # For stripping markdown symbols
from app.config import db  # MongoDB connection
from app.models.patient_models import MedicalRecord  # Assuming MedicalRecord model exists
from .auth_routes import get_current_authenticated_user

logger = logging.getLogger(__name__)
patient_router = APIRouter()

# --- TEMPLATES PATH ---
current_file_path = Path(__file__).resolve()
routes_dir = current_file_path.parent
app_dir = routes_dir.parent
templates_dir_path = app_dir / "templates"
templates = Jinja2Templates(directory=templates_dir_path)

# --- Initialize Gemini API ---
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')  # Adjust model as needed
    logger.info("Gemini API initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Gemini API: {e}", exc_info=True)
    gemini_model = None

# --- Wellness Plan Endpoint ---
@patient_router.get("/wellness", response_class=HTMLResponse, name="get_wellness_plan")
async def get_wellness_plan(
    request: Request,
    current_user: dict = Depends(get_current_authenticated_user)
):
    """
    Generates a personalized wellness plan for the authenticated patient using Gemini.
    Returns an HTML page displaying diet, habits, avoidances, and exercises in separate paragraphs.
    """
    if current_user.get("user_type") != "patient":
        logger.warning(f"Access denied for user {current_user.get('_id')} trying to access wellness plan.")
        raise HTTPException(status_code=403, detail="Access denied. Only patients can access this page.")

    patient_id = str(current_user.get('_id'))
    logger.info(f"Generating wellness plan for patient {patient_id}")

    # --- Fetch Patient and Medical Record ---
    try:
        if not ObjectId.is_valid(patient_id):
            logger.warning(f"Invalid patient ID format: {patient_id}")
            raise HTTPException(status_code=400, detail="Invalid patient ID format.")

        patient_oid = ObjectId(patient_id)
        patient_details = await db.patients.find_one({"_id": patient_oid})
        if not patient_details:
            logger.warning(f"Patient not found for ID: {patient_id}")
            raise HTTPException(status_code=404, detail="Patient not found.")

        medical_record_doc = await db.medical_records.find_one({"patient_id": patient_id})
        medical_record = medical_record_doc or {
            "patient_id": patient_id,
            "current_medications": [],
            "diagnoses": [],
            "prescriptions": [],
            "consultation_history": [],
            "reports": [],
            "allergies": [],
            "immunizations": [],
            "family_medical_history": None,
            "updated_at": None
        }

        # Fetch report contents for context
        if medical_record.get("reports"):
            updated_reports = []
            for report_ref in medical_record.get("reports", []):
                if isinstance(report_ref, dict) and report_ref.get("content_id"):
                    try:
                        if not ObjectId.is_valid(report_ref["content_id"]):
                            logger.warning(f"Invalid content ID format: {report_ref.get('content_id')}")
                            continue
                        content_oid = ObjectId(report_ref["content_id"])
                        report_content_doc = await db.report_contents.find_one({"_id": content_oid})
                        if report_content_doc and report_content_doc.get("content"):
                            report_with_content = report_ref.copy()
                            report_with_content["description"] = report_content_doc["content"]
                            updated_reports.append(report_with_content)
                    except Exception as e:
                        logger.warning(f"Error fetching report content for wellness plan: {e}")
            medical_record["reports"] = updated_reports

    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Error fetching patient data for wellness plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching patient data.")

    # --- Prepare Patient Data for Gemini ---
    patient_data = {
        "patient": patient_details,
        "medical_record": medical_record
    }

    # Format patient data as a string for Gemini
    patient_info_str = f"""
Patient Name: {patient_details.get('name', {}).get('first', '')} {patient_details.get('name', {}).get('last', '')}
Date of Birth: {patient_details.get('date_of_birth', 'N/A')}
Gender: {patient_details.get('gender', 'N/A')}
Diagnoses: {', '.join([d.get('name', '') if isinstance(d, dict) else str(d) for d in medical_record.get('diagnoses', [])]) or 'None'}
Current Medications: {', '.join([m.get('name', '') if isinstance(m, dict) else str(m) for m in medical_record.get('current_medications', [])]) or 'None'}
Allergies: {', '.join(medical_record.get('allergies', [])) or 'None'}
Immunizations: {', '.join([i.get('name', '') if isinstance(d, dict) else str(d) for d in medical_record.get('immunizations', [])]) or 'None'}
Family Medical History: {medical_record.get('family_medical_history', 'None')}
Recent Reports: {', '.join([r.get('description', '')[:100] for r in medical_record.get('reports', [])]) or 'None'}
"""

    # --- Generate Wellness Plan with Gemini ---
    if not gemini_model:
        logger.error("Gemini model not initialized.")
        raise HTTPException(status_code=503, detail="AI service unavailable.")

    prompt = f"""
Based on the following patient data, generate a personalized wellness plan. The plan must include four distinct sections, each in a separate paragraph, clearly labeled with plain text headers followed by a colon (e.g., 'Diet Recommendations:'). Do not use markdown symbols like **, *, or # in the headers or content. The sections are:
Diet Recommendations: Suggest a diet plan tailored to the patient's health conditions, allergies, and medical history. Include specific foods to eat and portion suggestions.
Healthy Habits: Recommend daily habits to improve overall health, tailored to the patient's condition and lifestyle.
Things to Avoid: List specific foods, activities, or behaviors to avoid based on the patient's medical history and allergies.
Exercise Plan: Provide an exercise routine suitable for the patient's condition, including type, duration, and frequency.

Ensure each section is specific, actionable, and tailored to the patient's data. Avoid generic advice. Return the response in plain text with clear section headers as specified.

Patient Data:
{patient_info_str}
"""

    try:
        response = await gemini_model.generate_content_async(prompt)
        wellness_plan_text = response.text.strip()

        # Strip any residual markdown symbols (e.g., *, **, #)
        wellness_plan_text = re.sub(r'[\*\#]+', '', wellness_plan_text)

        # Parse the response into sections
        sections = {
            "diet": "",
            "habits": "",
            "avoid": "",
            "exercise": ""
        }
        current_section = None
        for line in wellness_plan_text.split("\n"):
            line = line.strip()
            if line == "Diet Recommendations:":
                current_section = "diet"
                continue
            elif line == "Healthy Habits:":
                current_section = "habits"
                continue
            elif line == "Things to Avoid:":
                current_section = "avoid"
                continue
            elif line == "Exercise Plan:":
                current_section = "exercise"
                continue
            if current_section and line:
                sections[current_section] += line + " "

        # Ensure all sections have content
        for key, value in sections.items():
            if not value.strip():
                sections[key] = f"No specific {key.replace('_', ' ')} recommendations provided based on available data."

    except Exception as e:
        logger.error(f"Error generating wellness plan with Gemini: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating wellness plan: {e}")

    # --- Render Template ---
    return templates.TemplateResponse(
        "wellness.html",
        {
            "request": request,
            "patient": patient_details,
            "wellness_plan": sections
        }
    )