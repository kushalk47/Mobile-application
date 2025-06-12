# app/routes/doctor_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File, Request
from fastapi.responses import JSONResponse, StreamingResponse # Removed HTMLResponse, RedirectResponse
from typing import Optional, List, Dict, Any
from bson import ObjectId
from datetime import datetime
import logging
import io
import json

# Removed Jinja2Templates as we are no longer rendering HTML
# from fastapi.templating import Jinja2Templates
# templates = Jinja2Templates(directory="templates") # REMOVE THIS LINE ENTIRELY


# Imports for transcription/AI (if you still need them for other POST routes)
from fastapi.concurrency import run_in_threadpool
import anyio # Might not be needed if not running background tasks directly in route

# Imports for PDF generation (if you still need them for other POST routes)
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleNew, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Import your database utility and all necessary patient models
from app.database import get_database
from app.models.patient_models import (
    Patient, MedicalRecord, PatientData, PatientListItem,
    Report, ReportContent, ReportDisplay, # Ensure these are imported
    ChatRequest, ReportRequest, ReportPDFRequest, # Your request models
    Medication, Diagnosis, Consultation, Immunization # If used by other routes
)
# Assuming you have a proper doctor authentication dependency
from app.auth.auth_bearer import get_current_active_doctor

logger = logging.getLogger(__name__)
doctor_router = APIRouter()

# --- Endpoint 1: Get a list of all patients (JSON) ---
@doctor_router.get(
    "/patients",
    response_model=List[PatientListItem], # Returns a list of simplified patient objects
    summary="Get All Patients (Doctor Access Only)",
    response_description="Returns a list of all registered patients with basic details."
)
async def get_all_patients(
    db=Depends(get_database),
    current_doctor: dict = Depends(get_current_active_doctor) # Doctor authentication
):
    """
    Retrieves a list of all registered patients.
    Each patient entry includes their ID, email, and name.
    """
    patients_list = []
    try:
        # Fetch all patients, project only necessary fields for the list view
        cursor = db.patients.find({}, {"_id": 1, "email": 1, "name.first": 1, "name.last": 1, "phone_number": 1})
        async for patient_data in cursor:
            # Manually map fields to PatientListItem, extracting name components
            patients_list.append(PatientListItem(
                id=str(patient_data['_id']),
                email=patient_data.get('email', ''),
                first_name=patient_data.get('name', {}).get('first', ''),
                last_name=patient_data.get('name', {}).get('last', ''),
                contact_number=patient_data.get('phone_number')
            ))
        return patients_list
    except Exception as e:
        logger.error(f"Error fetching all patients: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal server error occurred while fetching patients: {e}"
        )


# --- Endpoint 2: Get a single patient's details and medical record (JSON) ---
@doctor_router.get(
    "/patients/{patient_id}",
    response_model=PatientData, # This is the combined model we expect to return
    summary="Get Patient Basic and Medical Details by ID (Doctor Access Only)",
    response_description="Returns patient's basic and medical record data in JSON format."
)
async def get_patient_details(
    patient_id: str, # Patient ID from the URL path
    db=Depends(get_database), # MongoDB database dependency
    current_doctor: dict = Depends(get_current_active_doctor) # Doctor authentication
):
    """
    Retrieves comprehensive details for a specific patient,
    including their basic profile and associated medical record.
    The response is JSON.

    Access is restricted to authenticated doctors.
    """
    try:
        if not ObjectId.is_valid(patient_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Patient ID format. Must be a valid ObjectId string."
            )

        patient_obj_id = ObjectId(patient_id)

        # 1. Fetch Patient's Basic Information from 'patients' collection
        patient_data = await db.patients.find_one({"_id": patient_obj_id})
        if not patient_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID '{patient_id}' not found."
            )
        patient_model = Patient(**patient_data)

        # 2. Fetch Patient's Medical Record from 'medical_records' collection
        medical_record_data = await db.medical_records.find_one({"patient_id": patient_id})

        if not medical_record_data:
            logger.info(f"No medical record found for patient ID: {patient_id}. Returning default empty record.")
            medical_record_model = MedicalRecord(patient_id=patient_id)
        else:
            medical_record_model = MedicalRecord(**medical_record_data)

        return PatientData(patient=patient_model, medical_record=medical_record_model)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred in get_patient_details for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal server error occurred: {e}"
        )

# --- Endpoint 3: Get a specific report's content (JSON) ---
@doctor_router.get(
    "/reports/{report_content_id}",
    response_model=ReportDisplay, # Returns the report metadata and its full content
    summary="Get Specific Report Content by ID (Doctor Access Only)",
    response_description="Returns the details and full text content of a specific report."
)
async def get_report_content(
    report_content_id: str, # The _id of the ReportContent document
    db=Depends(get_database),
    current_doctor: dict = Depends(get_current_active_doctor) # Doctor authentication
):
    """
    Retrieves the full content of a specific AI-generated or other report.
    This is typically linked from a MedicalRecord's list of reports.
    """
    try:
        if not ObjectId.is_valid(report_content_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Report Content ID format. Must be a valid ObjectId string."
            )

        report_content_obj_id = ObjectId(report_content_id)

        # Fetch the ReportContent document
        content_data = await db.report_contents.find_one({"_id": report_content_obj_id})
        if not content_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report content with ID '{report_content_id}' not found."
            )
        report_content_model = ReportContent(**content_data)

        # Optionally, you might want to fetch the parent Report metadata as well
        # This assumes a way to link back, e.g., finding a Report in any MedicalRecord
        # that has this content_id. This query might be complex if not directly indexed.
        # For simplicity, we'll try to find the first Report linking to this content_id.
        report_info = await db.medical_records.find_one(
            {"reports.content_id": report_content_id},
            {"reports.$": 1} # Project only the matched report element
        )

        report_model = None
        if report_info and "reports" in report_info and report_info["reports"]:
            # Extract the actual report dictionary from the nested structure
            raw_report_data = report_info["reports"][0]
            report_model = Report(**raw_report_data)
        else:
            # If no linking Report found, create a dummy one or raise error
            logger.warning(f"No parent Report metadata found for content_id: {report_content_id}. Returning default Report info.")
            report_model = Report(
                report_id=report_content_id, # Use content_id as report_id if no other ID available
                report_type="Unknown",
                date=datetime.utcnow(),
                content_id=report_content_id
            )

        return ReportDisplay(report_info=report_model, report_content=report_content_model)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred in get_report_content for ID {report_content_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal server error occurred: {e}"
        )


# --- Your existing POST routes (e.g., /process-report, /save-report-text, etc.) ---
# Ensure these continue to return JSONResponse as they likely already do.
# I'm including the snippets you previously shared to make this a complete file.

@doctor_router.post("/process-report/{patient_id}", summary="Process an audio report and generate text (Doctor Access Only)")
async def process_report_audio(
    request: Request, # Request object to get context for templates if needed for redirect logic
    patient_id: str,
    audio_file: UploadFile = File(..., description="Audio file of the patient's consultation."),
    db=Depends(get_database),
    current_doctor: dict = Depends(get_current_active_doctor) # Doctor authentication
):
    logger.info(f"Received audio file for patient {patient_id}: {audio_file.filename}, size: {audio_file.size}")
    if not ObjectId.is_valid(patient_id):
        raise HTTPException(status_code=400, detail="Invalid patient_id format.")

    try:
        # Mock transcription process (replace with actual Whisper/AI integration)
        transcribed_text = f"This is a mock transcription of an audio report for patient {patient_id}. " \
                           f"The original file was {audio_file.filename}."
        logger.info(f"Mock transcription generated for {patient_id}")

        # Store the raw transcribed text in the 'report_contents' collection
        content_doc = {
            "content": transcribed_text,
            "created_at": datetime.utcnow()
        }
        insert_result = await db.report_contents.insert_one(content_doc)
        content_id = str(insert_result.inserted_id)
        logger.info(f"Transcribed text saved to report_contents with ID: {content_id}")

        # This response can guide the frontend to a page where the text can be edited
        # and then saved, or directly rendered.
        return JSONResponse({
            "message": "Audio processed and text generated successfully",
            "patient_id": patient_id,
            "transcribed_text": transcribed_text, # Frontend might want this for immediate display/editing
            "content_id": content_id # Important for linking later if text is saved
        })

    except Exception as e:
        logger.error(f"Error processing audio report for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process audio report: {e}")


@doctor_router.post("/save-report-text/{patient_id}", summary="Save AI-generated report text (Doctor Access Only)")
async def save_report_text(
    patient_id: str,
    report_data: ReportPDFRequest, # Reusing ReportPDFRequest as it carries report_content_text
    db=Depends(get_database),
    current_doctor: dict = Depends(get_current_active_doctor) # Doctor authentication
):
    logger.info(f"Received save report text request for patient {patient_id}")
    if not ObjectId.is_valid(patient_id):
        raise HTTPException(status_code=400, detail="Invalid patient_id format.")

    try:
        patient_obj_id = ObjectId(patient_id)
        report_content = report_data.report_content_text
        current_time = datetime.utcnow()

        # Assuming the ReportPDFRequest might carry content_id if it's an update
        content_id_from_request = getattr(report_data, 'content_id', None)

        # Find or create a medical record for the patient
        medical_record = await db.medical_records.find_one({"patient_id": patient_id})
        if not medical_record:
            # Create a new medical record if it doesn't exist
            new_record = MedicalRecord(patient_id=patient_id)
            await db.medical_records.insert_one(new_record.dict(by_alias=True))
            logger.info(f"Created new medical record for patient {patient_id}")

        # Decide whether to insert new report content or update existing
        if content_id_from_request and ObjectId.is_valid(content_id_from_request):
            # Update existing report content
            await db.report_contents.update_one(
                {"_id": ObjectId(content_id_from_request)},
                {"$set": {"content": report_content, "last_updated": current_time}}
            )
            content_db_id = ObjectId(content_id_from_request)
            logger.info(f"Updated existing report content with ID: {content_id_from_request}")
        else:
            # Insert new report content
            content_doc = {"content": report_content, "created_at": current_time}
            insert_result = await db.report_contents.insert_one(content_doc)
            content_db_id = insert_result.inserted_id
            logger.info(f"Inserted new report content with ID: {content_db_id}")

        # Create a new Report entry to be added to the medical record
        # You'll need to define how 'report_type' is determined (e.g., from frontend or fixed)
        new_report_entry = Report(
            report_id=str(ObjectId()), # Generate a unique ID for this report entry
            report_type="AI Generated Consultation", # Example type
            date=current_time,
            content_id=str(content_db_id) # Link to the stored content
        )

        # Update the patient's medical record to include this new report
        update_result = await db.medical_records.update_one(
            {"patient_id": patient_id},
            {"$push": {"reports": new_report_entry.dict()}} # Add the report entry to the reports array
        )
        if update_result.matched_count == 0:
            logger.error(f"Medical record not found for update for patient {patient_id}.")
            raise HTTPException(status_code=500, detail="Internal server error: Medical record not found for update.")

        logger.info(f"Report entry added to medical record for patient {patient_id}")

        return JSONResponse({"message": "Report text saved and linked to medical record successfully", "report_content_id": str(content_db_id)})

    except Exception as e:
        logger.error(f"Error saving report text for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save report text: {e}")

# --- PDF Generation Endpoint (retained from your previous code, returns a stream) ---
@doctor_router.post("/generate-pdf/{patient_id}", summary="Generate a PDF report from AI text (Doctor Access Only)")
async def generate_pdf(
    patient_id: str,
    report_data: ReportPDFRequest, # Expects report_content_text
    db=Depends(get_database), # Assuming you need db access here (e.g., to fetch patient data for header)
    current_doctor: dict = Depends(get_current_active_doctor) # Doctor authentication
):
    logger.info(f"Received PDF generation request for patient {patient_id}")
    if not ObjectId.is_valid(patient_id):
        raise HTTPException(status_code=400, detail="Invalid patient_id format.")

    try:
        # Fetch patient details for PDF header (optional but good practice)
        patient_info = await db.patients.find_one({"_id": ObjectId(patient_id)})
        patient_name = "Patient"
        patient_dob = "N/A"
        if patient_info:
            patient_name = f"{patient_info.get('name', {}).get('first', '')} {patient_info.get('name', {}).get('last', '')}"
            patient_dob = patient_info.get('date_of_birth', 'N/A')

        report_content_text = report_data.report_content_text

        # Create a PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Add title
        title_style = ParagraphStyle(
            name='TitleStyle',
            parent=styles['h1'],
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=14
        )
        story.append(Paragraph("Aarogya AI - Medical Report", title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Add patient details
        header_style = ParagraphStyle(
            name='HeaderStyle',
            parent=styles['Normal'],
            fontSize=12,
            alignment=TA_LEFT,
            spaceAfter=6
        )
        story.append(Paragraph(f"<b>Patient Name:</b> {patient_name}", header_style))
        story.append(Paragraph(f"<b>Patient ID:</b> {patient_id}", header_style))
        story.append(Paragraph(f"<b>Date of Birth:</b> {patient_dob}", header_style))
        story.append(Paragraph(f"<b>Report Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", header_style))
        story.append(Spacer(1, 0.4 * inch))

        # Add report content
        content_style = ParagraphStyle(
            name='ContentStyle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            leading=14,
            spaceAfter=12
        )
        # Split text into paragraphs
        paragraphs = report_content_text.split('\n')
        for p_text in paragraphs:
            if p_text.strip(): # Only add non-empty lines
                story.append(Paragraph(p_text, content_style))
                story.append(Spacer(1, 0.1 * inch))

        doc.build(story)
        buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=medical_report_{patient_id}.pdf"}
        )

    except Exception as e:
        logger.error(f"Error generating PDF for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e}")