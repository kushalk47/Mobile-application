# app/routes/appointment_route.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone
from typing import Optional, List
from bson import ObjectId
import logging
import os
import google.generativeai as genai  # Gemini API
import re  # For cleaning Gemini response

# Import models
from app.models.appointment_models import Appointment
from app.models.doctor_models import Doctor
from app.models.patient_models import Patient, MedicalRecord

# Import db connection
from app.config import db

# Import authentication dependency
from app.routes.auth_routes import get_current_authenticated_user

# Setup templates path
from pathlib import Path
current_file_path = Path(__file__).resolve()
routes_dir = current_file_path.parent
app_dir = routes_dir.parent
templates_dir_path = app_dir / "templates"
templates = Jinja2Templates(directory=templates_dir_path)

# Logging setup
logger = logging.getLogger(__name__)

# Define the router
appointment_router = APIRouter()

# --- Initialize Gemini API ---
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')  # Consistent with patient_routes.py
    logger.info("Gemini API initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Gemini API: {e}", exc_info=True)
    gemini_model = None

# --- Helper Dependency to get current *Patient* ---
async def get_current_patient(current_user: dict = Depends(get_current_authenticated_user)):
    """Dependency to get the current authenticated patient user document."""
    if current_user.get("user_type") != "patient":
        raise HTTPException(status_code=403, detail="Only patients can access this page.")
    return current_user

# --- Helper function to fetch patient's appointments with doctor names ---
async def fetch_patient_appointments_with_doctor_names(patient_id_str: str):
    """Fetches appointments for a patient and adds doctor names."""
    appointments_cursor = db.appointments.find({"patient_id": patient_id_str}).sort("appointment_time", 1)
    appointments_list_raw = await appointments_cursor.to_list(length=1000)

    appointments_with_names = []
    for appointment_doc in appointments_list_raw:
        try:
            doctor_id_str = appointment_doc.get("doctor_id")
            doctor_doc = None
            if doctor_id_str:
                try:
                    doctor_doc = await db.doctors.find_one({"_id": ObjectId(doctor_id_str)})
                except Exception as e:
                    logger.warning(f"Error converting doctor_id '{doctor_id_str}' to ObjectId for appointment {appointment_doc.get('_id')}: {e}")

            if doctor_doc:
                appointment_doc["doctor_name"] = f"Dr. {doctor_doc.get('name', {}).get('first', '')} {doctor_doc.get('name', {}).get('last', '')}".strip()
            else:
                appointment_doc["doctor_name"] = "Unknown Doctor"

            appointments_with_names.append(appointment_doc)

        except Exception as doctor_fetch_error:
            logger.warning(f"Error fetching doctor for appointment {appointment_doc.get('_id')}: {doctor_fetch_error}")
            appointment_doc["doctor_name"] = "Error Doctor Fetch"
            appointments_with_names.append(appointment_doc)

    return appointments_with_names

# --- Helper function to predict symptom severity with Gemini ---
async def predict_symptom_severity(medical_record: dict, reason: Optional[str], patient_notes: Optional[str]) -> str:
    """Uses Gemini to predict symptom severity based on medical record, reason, and patient notes."""
    if not gemini_model:
        logger.error("Gemini model not initialized.")
        return "Unknown"  # Fallback if Gemini is unavailable

    # Format medical record for Gemini
    medical_info_str = f"""
Medical Record:
Diagnoses: {', '.join([d.get('name', '') if isinstance(d, dict) else str(d) for d in medical_record.get('diagnoses', [])]) or 'None'}
Current Medications: {', '.join([m.get('name', '') if isinstance(m, dict) else str(m) for m in medical_record.get('current_medications', [])]) or 'None'}
Allergies: {', '.join(medical_record.get('allergies', [])) or 'None'}
Immunizations: {', '.join([i.get('name', '') if isinstance(i, dict) else str(i) for i in medical_record.get('immunizations', [])]) or 'None'}
Family Medical History: {medical_record.get('family_medical_history', 'None')}
Recent Reports: {', '.join([r.get('description', '')[:100] for r in medical_record.get('reports', [])]) or 'None'}
Reason for Visit: {reason or 'Not provided'}
Symptoms Description: {patient_notes or 'Not provided'}
"""

    prompt = f"""
Based on the following patient medical information, predict the severity of the symptoms described. Return only one of the following severity levels as plain text: 'Very Serious', 'Moderate', 'Normal'. Do not include any explanations, markdown symbols, or additional text. Analyze the diagnoses, medications, allergies, family medical history, reason for visit, and symptoms description to make an informed prediction.

{medical_info_str}
"""

    try:
        response = await gemini_model.generate_content_async(prompt)
        severity = response.text.strip()
        # Validate the response
        valid_severities = ["Very Serious", "Moderate", "Normal"]
        if severity not in valid_severities:
            logger.warning(f"Invalid severity response from Gemini: {severity}")
            return "Unknown"
        return severity
    except Exception as e:
        logger.error(f"Error predicting symptom severity with Gemini: {e}", exc_info=True)
        return "Unknown"  # Fallback on error

# ---------------------- Patient Book Appointment & View Appointments Page (GET) ----------------------
@appointment_router.get("/book-appointment", response_class=HTMLResponse)
async def get_book_and_view_appointments_page(
    request: Request,
    current_patient: dict = Depends(get_current_patient)
):
    """Renders the combined book appointment and view appointments page."""
    patient_id_str = str(current_patient["_id"])

    try:
        # Fetch all doctors for the booking form
        doctors_cursor = db.doctors.find({})
        doctors_list_raw = await doctors_cursor.to_list(length=1000)

        # Fetch the patient's appointments for the list section
        patient_appointments = await fetch_patient_appointments_with_doctor_names(patient_id_str)

    except Exception as e:
        logger.error(f"Error fetching data for combined page: {e}")
        return templates.TemplateResponse(
            "book_appointment.html",
            {
                "request": request,
                "error": "Could not load page data.",
                "doctors": [],
                "appointments": [],
                "patient": current_patient
            }
        )

    return templates.TemplateResponse(
        "book_appointment.html",
        {
            "request": request,
            "doctors": doctors_list_raw,
            "appointments": patient_appointments,
            "patient": current_patient
        }
    )

# ---------------------- Create Appointment (POST) ----------------------
@appointment_router.post("/book-appointment")
async def create_appointment(
    request: Request,
    current_patient: dict = Depends(get_current_patient),
    doctor_id: str = Form(...),
    appointment_date: str = Form(...),
    appointment_time: str = Form(...),
    reason: Optional[str] = Form(None),
    patient_notes: Optional[str] = Form(None),
):
    """Handles the submission of the book appointment form, predicts symptom severity, and re-renders the page."""
    patient_id_str = str(current_patient["_id"])

    # Combine date and time strings into a datetime object
    try:
        datetime_str = f"{appointment_date} {appointment_time}"
        appointment_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        appointment_time_utc = appointment_dt.replace(tzinfo=timezone.utc)
    except ValueError as e:
        logger.warning(f"Date/time parsing error: {e}")
        doctors_list_raw = await db.doctors.find({}).to_list(length=1000)
        patient_appointments = await fetch_patient_appointments_with_doctor_names(patient_id_str)
        return templates.TemplateResponse(
            "book_appointment.html",
            {
                "request": request,
                "error": "Invalid date or time format. Please use YYYY-MM-DD and HH:MM.",
                "doctors": doctors_list_raw,
                "appointments": patient_appointments,
                "patient": current_patient
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error during date/time processing: {e}")
        doctors_list_raw = await db.doctors.find({}).to_list(length=1000)
        patient_appointments = await fetch_patient_appointments_with_doctor_names(patient_id_str)
        return templates.TemplateResponse(
            "book_appointment.html",
            {
                "request": request,
                "error": "An error occurred processing the date or time.",
                "doctors": doctors_list_raw,
                "appointments": patient_appointments,
                "patient": current_patient
            }
        )

    # Fetch patient’s medical record
    try:
        medical_record_doc = await db.medical_records.find_one({"patient_id": patient_id_str})
        medical_record = medical_record_doc or {
            "patient_id": patient_id_str,
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
                        logger.warning(f"Error fetching report content for severity prediction: {e}")
            medical_record["reports"] = updated_reports

    except Exception as e:
        logger.error(f"Error fetching medical record for patient {patient_id_str}: {e}")
        medical_record = {
            "patient_id": patient_id_str,
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

    # Predict symptom severity using Gemini
    predicted_severity = await predict_symptom_severity(medical_record, reason, patient_notes)

    # Create the appointment data dictionary
    appointment_data = {
        "patient_id": patient_id_str,
        "doctor_id": doctor_id,
        "appointment_time": appointment_time_utc,
        "reason": reason,
        "patient_notes": patient_notes,
        "status": "Scheduled",
        "gmeet_link": None,
        "predicted_severity": predicted_severity,  # Store predicted severity
        "created_at": datetime.now(timezone.utc)
    }

    try:
        # Insert the new appointment into the database
        insert_result = await db.appointments.insert_one(appointment_data)
        if not insert_result.inserted_id:
            raise Exception("Failed to insert appointment into database.")
        logger.info(f"Appointment created with ID: {insert_result.inserted_id}, Predicted Severity: {predicted_severity}")

    except Exception as e:
        logger.error(f"Database error during appointment creation: {e}")
        doctors_list_raw = await db.doctors.find({}).to_list(length=1000)
        patient_appointments = await fetch_patient_appointments_with_doctor_names(patient_id_str)
        return templates.TemplateResponse(
            "book_appointment.html",
            {
                "request": request,
                "error": f"Error booking appointment: {e}",
                "doctors": doctors_list_raw,
                "appointments": patient_appointments,
                "patient": current_patient
            }
        )

    # Re-render the page after successful booking
    doctors_list_raw = await db.doctors.find({}).to_list(length=1000)
    patient_appointments = await fetch_patient_appointments_with_doctor_names(patient_id_str)
    return templates.TemplateResponse(
        "book_appointment.html",
        {
            "request": request,
            "success_message": f"Appointment booked successfully! Predicted symptom severity: {predicted_severity}",
            "doctors": doctors_list_raw,
            "appointments": patient_appointments,
            "patient": current_patient
        }
    )