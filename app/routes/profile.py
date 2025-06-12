# app/routes/profile.py
from fastapi import APIRouter, Request, Depends, HTTPException, Response
from typing import Optional, List
from bson import ObjectId, errors
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Define APIRouter FIRST
profile_router = APIRouter()

# Import db from the config module
from app.config import db

# Import the authentication dependency
from .auth_routes import get_current_authenticated_user

# Import models for type hinting (optional but good practice)
# Make sure app.models.patient_models.Patient is a pydantic BaseModel
from app.models.patient_models import Patient, MedicalRecord, Report, ReportContent
from app.models.doctor_models import Doctor


@profile_router.get("/me") # Changed path to /me for clarity and consistency
async def get_profile(
    request: Request,
    current_user_doc: dict = Depends(get_current_authenticated_user)
):
    """
    Returns the patient's profile as JSON, including medical details.
    Requires authentication.
    """
    is_patient = current_user_doc.get("user_type") == "patient"

    if not is_patient:
        if current_user_doc.get("user_type") == "doctor":
            # For doctors, you might return a message or redirect to a doctor dashboard API
            raise HTTPException(status_code=403, detail="Access denied. Doctors have a different profile endpoint.")
        else:
            raise HTTPException(status_code=403, detail="Access denied. Only patients can view this profile.")

    # --- Fetch Patient Details ---
    patient_details = current_user_doc.copy()
    patient_details["id"] = str(patient_details["_id"]) # Rename _id to id for frontend compatibility
    del patient_details["_id"] # Remove the MongoDB ObjectId

    # --- Fetch Medical Record ---
    patient_id_str = patient_details["id"] # Use the string id
    medical_record_doc = await db.medical_records.find_one({"patient_id": patient_id_str})

    # Initialize medical_record_data for the response
    medical_record_data = None

    if medical_record_doc:
        # Prepare medical record for JSON response
        medical_record_data = medical_record_doc.copy()
        medical_record_data["id"] = str(medical_record_data["_id"]) # Convert medical record _id to string
        del medical_record_data["_id"]

        # --- Fetch Report Contents and embed them ---
        if medical_record_data.get("reports"):
            updated_reports = []
            for report_ref in medical_record_data["reports"]:
                if isinstance(report_ref, dict) and report_ref.get("content_id"):
                    try:
                        content_oid = ObjectId(report_ref["content_id"])
                        report_content_doc = await db.report_contents.find_one({"_id": content_oid})

                        if report_content_doc and report_content_doc.get("content"):
                            report_with_content = report_ref.copy()
                            report_with_content["description"] = report_content_doc["content"]
                            if '_id' in report_with_content: # Ensure _id is handled for nested docs if present
                                report_with_content['id'] = str(report_with_content['_id'])
                                del report_with_content['_id']
                            if 'content_id' in report_with_content: # Ensure content_id is handled if present
                                report_with_content['content_id'] = str(report_with_content['content_id'])
                            updated_reports.append(report_with_content)
                        else:
                            logger.warning(f"Report content not found for content_id: {report_ref['content_id']}")
                            # If content is missing, you might still want to include the report reference
                            # or filter it out based on your application's needs.
                            # For now, it will be skipped if content is essential.
                    except errors.InvalidId:
                        logger.warning(f"Invalid content_id format in report reference: {report_ref.get('content_id')}")
                    except Exception as e:
                        logger.error(f"Error fetching report content for content_id {report_ref.get('content_id')}: {e}")
            medical_record_data["reports"] = updated_reports
        else:
             medical_record_data["reports"] = [] # Ensure reports is an empty list if not present or no content

    # Construct the JSON response
    response_data = {
        "patient": patient_details,
        "medical_record": medical_record_data, # This will be None if no medical record found
    }

    return response_data