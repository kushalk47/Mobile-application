# app/routes/auth_routes.py
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request, Form, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from bson import ObjectId
from typing import Optional, List, Dict, Any
import logging

# Logging setup (keep this if you haven't set it in main.py)
logger = logging.getLogger(__name__)

# Import models from the 'app.models' package
from app.models.patient_models import Patient, PatientCreate
from app.models.doctor_models import Doctor

# Import db directly from the 'app.config' module where it is defined
from app.config import db

# Import sessions from the 'app.models' package
from app.models.sessions import create_user_session, delete_user_session, get_current_session, UserSession, SESSION_COOKIE_NAME, SESSION_EXPIRATION_MINUTES
from passlib.hash import bcrypt

auth_router = APIRouter()

# ---------------------- API Response Models ----------------------

class AuthResponse(BaseModel):
    """
    Standard response model for authentication operations.
    """
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class UserSchema(BaseModel):
    """
    Schema for returning basic user information after login/signup.
    """
    id: str
    email: str
    user_type: str
    name: Optional[Dict[str, str]] = None


# ---------------------- Utility Functions ----------------------

def hash_password(password: str) -> str:
    if isinstance(password, str):
        password = password.encode('utf-8')
    return bcrypt.hash(password).decode('utf-8')

def verify_password(raw_password: str, hashed_password: str) -> bool:
    if isinstance(hashed_password, bytes):
        hashed_password = hashed_password.decode('utf-8')
    if isinstance(raw_password, str):
        raw_password = raw_password.encode('utf-8')
    return bcrypt.verify(raw_password, hashed_password)

# Dependency to get the current authenticated user (Patient or Doctor)
async def get_current_authenticated_user(request: Request):
    # --- ADD THIS DEBUG LINE ---
    logger.debug(f"DEBUG: get_current_authenticated_user - Raw cookies received: {request.cookies}")
    # --- END DEBUG LINE ---

    session: Optional[UserSession] = await get_current_session(request)

    if not session:
        logger.debug("No valid session found by get_current_session. Raising 401.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: No valid session found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = session.user_id
    user_doc = None
    logger.debug(f"Session found. User ID from session: {user_id_str}, User Type: {session.user_type}")

    try:
        object_id = ObjectId(user_id_str)
        if session.user_type == "patient":
            logger.debug(f"Attempting to find patient with _id: {user_id_str}")
            user_doc = await db.patients.find_one({"_id": object_id})
            logger.debug(f"Patient document found: {user_doc is not None}")
        elif session.user_type == "doctor":
            logger.debug(f"Attempting to find doctor with _id: {user_id_str}")
            user_doc = await db.doctors.find_one({"_id": object_id})
            logger.debug(f"Doctor document found: {user_doc is not None}")
    except Exception as e:
        logger.error(f"Error fetching user {user_id_str} of type {session.user_type}: {e}")
        user_doc = None

    if not user_doc:
        logger.warning(f"User document not found for session user_id {user_id_str}. Session might be invalid.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: User not found or session invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("User document found. Authentication successful.")
    return user_doc

# ---------------------- Signup Routes ----------------------

@auth_router.post("/signup", response_model=AuthResponse)
async def post_signup(
    request: Request,
    response: Response,
    first: str = Form(...),
    middle: Optional[str] = Form(None),
    last: str = Form(...),
    email: str = Form(...),
    phone_number: str = Form(...),
    password: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    street: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    zip: str = Form(...),
    country: str = Form(...),
    emergency_name: str = Form(...),
    emergency_phone: str = Form(...),
    emergency_relationship: str = Form(...),
    current_medications_text: Optional[str] = Form(None),
    diagnoses_text: Optional[str] = Form(None),
    prescriptions_text: Optional[str] = Form(None),
    consultation_history_text: Optional[str] = Form(None),
    reports_text: Optional[str] = Form(None),
    allergies_text: Optional[str] = Form(None),
    immunizations_text: Optional[str] = Form(None),
    family_medical_history: Optional[str] = Form(None)
):
    # Check if user already exists
    existing_patient = await db.patients.find_one({"email": email})
    existing_doctor = await db.doctors.find_one({"email": email})
    if existing_patient or existing_doctor:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=AuthResponse(success=False, message="Email already registered.").model_dump()
        )

    patient_oid = ObjectId()
    patient_id_str = str(patient_oid)

    hashed_pw = hash_password(password)

    patient_data = {
        "_id": patient_oid,
        "name": {"first": first, "middle": middle, "last": last},
        "email": email,
        "phone_number": phone_number,
        "password": hashed_pw,
        "age": age,
        "gender": gender,
        "address": {"street": street, "city": city, "state": state, "zip": zip, "country": country},
        "emergency_contact": {"name": emergency_name, "phone": emergency_phone, "relationship": emergency_relationship},
        "registration_date": datetime.now(timezone.utc),
        "user_type": "patient"
    }

    try:
        insert_result = await db.patients.insert_one(patient_data)
        if not insert_result.inserted_id:
            raise Exception("Failed to insert patient into database.")
        logger.info(f"Patient created with _id: {insert_result.inserted_id}")
    except Exception as e:
        logger.error(f"Database error during patient creation: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=AuthResponse(success=False, message="Error saving patient details. Please try again.").model_dump()
        )

    # --- Create Initial Medical Record (Step 2 Data) ---
    medical_record_data = {
        "_id": ObjectId(),
        "patient_id": patient_id_str,
        "current_medications": [m.strip() for m in current_medications_text.split(',') if m.strip()] if current_medications_text else [],
        "diagnoses": [d.strip() for d in diagnoses_text.split(',') if d.strip()] if diagnoses_text else [],
        "prescriptions": [p.strip() for p in prescriptions_text.split(',') if p.strip()] if prescriptions_text else [],
        "consultation_history": [c.strip() for c in consultation_history_text.split(',') if c.strip()] if consultation_history_text else [],
        "reports": [r.strip() for r in reports_text.split(',') if r.strip()] if reports_text else [],
        "allergies": [a.strip() for a in allergies_text.split(',') if a.strip()] if allergies_text else [],
        "immunizations": [i.strip() for i in immunizations_text.split(',') if i.strip()] if immunizations_text else [],
        "family_medical_history": family_medical_history,
    }
    try:
        await db.medical_records.insert_one(medical_record_data)
        logger.info(f"Medical record created for patient ID: {patient_id_str}")
    except Exception as e:
        logger.error(f"Error saving medical record for patient {patient_id_str}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=AuthResponse(success=False, message="Signup successful but failed to save medical record. Please contact support.").model_dump()
        )

    # --- Automatic Login after Successful Signup ---
    try:
        session_token = await create_user_session(user_id=patient_id_str, user_type="patient")
        logger.info(f"Session created after signup for user {patient_id_str}. Token (first 8 chars): {session_token[:8]}...")
    except Exception as e:
        logger.error(f"Error creating session after signup for user {patient_id_str}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=AuthResponse(success=False, message="Signup successful but failed to create session. Please try logging in.").model_dump()
        )

    # Set the cookie directly on the response object for successful signup & auto-login
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        max_age=SESSION_EXPIRATION_MINUTES * 60,
        path="/",
        secure=request.url.scheme == "https",
        samesite="Lax"
    )

    # Prepare user data for response, ensuring 'name' dictionary is clean
    processed_name_for_response = {"first": first, "middle": middle, "last": last}
    if processed_name_for_response.get('middle') is None:
        processed_name_for_response['middle'] = ""
    # Ensure all values are strings
    for key, value in processed_name_for_response.items():
        if value is None:
            processed_name_for_response[key] = ""
        elif not isinstance(value, str):
            processed_name_for_response[key] = str(value)

    user_data = UserSchema(
        id=patient_id_str,
        email=email,
        user_type="patient",
        name=processed_name_for_response
    ).model_dump()

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=AuthResponse(success=True, message="Signup successful. Welcome!", data=user_data).model_dump()
    )


# ---------------------- Login Routes ----------------------

@auth_router.post("/login", response_model=AuthResponse)
async def post_login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...)
):
    # --- ADD THIS DEBUG LINE ---
    logger.debug(f"DEBUG: /login - Raw cookies received: {request.cookies}")
    # --- END DEBUG LINE ---

    user_doc = None
    user_type = None
    user_id_str = None

    # Attempt to find patient
    patient_doc = await db.patients.find_one({"email": email})
    if patient_doc and verify_password(password, patient_doc.get("password")):
        user_doc = patient_doc
        user_type = "patient"
        user_id_str = str(user_doc["_id"])

    # If not patient, attempt to find doctor
    if not user_doc:
        doctor_doc = await db.doctors.find_one({"email": email})
        if doctor_doc and verify_password(password, doctor_doc.get("password")):
            user_doc = doctor_doc
            user_type = "doctor"
            user_id_str = str(user_doc["_id"])

    if not user_doc:
        logger.warning(f"Failed login attempt for email: {email}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=AuthResponse(success=False, message="Invalid email or password.").model_dump()
        )

    # --- Successful Login ---
    try:
        session_token = await create_user_session(user_id=user_id_str, user_type=user_type)
        logger.info(f"Session created after login for user {user_id_str}. Token (first 8 chars): {session_token[:8]}...")
    except Exception as e:
        logger.error(f"Error creating session after login for user {user_id_str}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=AuthResponse(success=False, message="Login successful but failed to create session. Please try again.").model_dump()
        )

    # Set the cookie for successful login
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        max_age=SESSION_EXPIRATION_MINUTES * 60,
        path="/",
        secure=request.url.scheme == "https",
        samesite="Lax"
    )

    # Prepare user data for response, ensuring 'name' dictionary is clean
    user_name_data = user_doc.get("name")
    processed_name_data: Optional[Dict[str, str]] = None
    if user_name_data:
        # Create a mutable copy to modify
        processed_name_data = user_name_data.copy()
        if 'middle' not in processed_name_data or processed_name_data['middle'] is None:
            processed_name_data['middle'] = ""
        # Ensure all values in the dictionary are strings if the schema is Dict[str, str]
        for key, value in processed_name_data.items():
            if value is None:
                processed_name_data[key] = ""
            elif not isinstance(value, str):
                processed_name_data[key] = str(value)

    user_data = UserSchema(
        id=user_id_str,
        email=email,
        user_type=user_type,
        name=processed_name_data
    ).model_dump()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthResponse(success=True, message="Login successful.", data=user_data).model_dump()
    )


# ---------------------- Logout ----------------------

@auth_router.post("/logout", response_model=AuthResponse)
async def logout(request: Request, response: Response):
    await delete_user_session(request, response)
    logger.info("User logged out.")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthResponse(success=True, message="Logged out successfully.").model_dump()
    )


# --- Protected routes (Examples) ---

@auth_router.get("/dashboard", response_model=AuthResponse)
async def dashboard(current_user: Dict[str, Any] = Depends(get_current_authenticated_user)):
    user_name = current_user.get("name", {}).get("first", "User")
    user_type = current_user.get("user_type", "Unknown")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthResponse(
            success=True,
            message="Dashboard access granted.",
            data={"user_name": user_name, "user_type": user_type, "user_details": current_user}
        ).model_dump()
    )

@auth_router.get("/profile", response_model=AuthResponse)
async def profile(current_user: Dict[str, Any] = Depends(get_current_authenticated_user)):
    user_details = {
        "id": str(current_user["_id"]),
        "email": current_user["email"],
        "user_type": current_user["user_type"],
        "name": current_user.get("name"),
        "phone_number": current_user.get("phone_number"),
        "age": current_user.get("age"),
        "gender": current_user.get("gender"),
        "address": current_user.get("address"),
        "emergency_contact": current_user.get("emergency_contact"),
        "registration_date": current_user.get("registration_date")
    }

    # Process 'name' data within user_details for consistent output
    if user_details.get("name"):
        processed_profile_name = user_details["name"].copy()
        if processed_profile_name.get('middle') is None:
            processed_profile_name['middle'] = ""
        for key, value in processed_profile_name.items():
            if value is None:
                processed_profile_name[key] = ""
            elif not isinstance(value, str):
                processed_profile_name[key] = str(value)
        user_details['name'] = processed_profile_name


    # If it's a patient, you might want to fetch and include medical records
    if current_user["user_type"] == "patient":
        medical_record = await db.medical_records.find_one({"patient_id": str(current_user["_id"])})
        if medical_record:
            # Convert ObjectId in medical_record to string
            medical_record['_id'] = str(medical_record['_id'])
            # Ensure reports within medical_record are processed for content
            if medical_record.get("reports"):
                updated_reports = []
                for report_ref in medical_record["reports"]:
                    if isinstance(report_ref, dict) and report_ref.get("content_id"):
                        try:
                            content_oid = ObjectId(report_ref["content_id"])
                            report_content_doc = await db.report_contents.find_one({"_id": content_oid})

                            if report_content_doc and report_content_doc.get("content"):
                                report_with_content = report_ref.copy()
                                report_with_content["description"] = report_content_doc["content"]
                                if '_id' in report_with_content:
                                    report_with_content['id'] = str(report_with_content['_id'])
                                    del report_with_content['_id']
                                if 'content_id' in report_with_content:
                                    report_with_content['content_id'] = str(report_with_content['content_id'])
                                updated_reports.append(report_with_content)
                            else:
                                logger.warning(f"Report content not found for content_id: {report_ref['content_id']}")
                        except errors.InvalidId:
                            logger.warning(f"Invalid content_id format in report reference: {report_ref.get('content_id')}")
                        except Exception as e:
                            logger.error(f"Error fetching report content for content_id {report_ref.get('content_id')}: {e}")
                medical_record["reports"] = updated_reports
            else:
                medical_record["reports"] = [] # Ensure reports is an empty list if not present

            user_details['medical_record'] = medical_record


    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthResponse(
            success=True,
            message="Profile data retrieved.",
            data=user_details
        ).model_dump()
    )