# app/routes/doctor_routes.py
from fastapi import APIRouter, Request, Depends, HTTPException, Form # Import Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse # Ensure JSONResponse is imported
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone
from bson import ObjectId # Ensure ObjectId is imported

# Import db connection
from app.config import db # Assuming 'db' is your Motor database client instance

# Import models
from app.models.appointment_models import Appointment # Assuming you have the updated Appointment model
from app.models.patient_models import Patient # Import Patient model to fetch patient names
# Assuming Doctor model is already imported or available if needed directly


# Import authentication dependency
# Adjust the import path based on where your get_current_authenticated_user is defined
from app.routes.auth_routes import get_current_authenticated_user


# Setup templates path (similar to other route files)
from pathlib import Path
current_file_path = Path(__file__).resolve()
routes_dir = current_file_path.parent
app_dir = routes_dir.parent
templates_dir_path = app_dir / "templates"
templates = Jinja2Templates(directory=templates_dir_path)

# Define the router (assuming it's already defined and maybe has a prefix like /dashboard)
# If your router is already defined elsewhere in this file, just add routes to it.
# Assuming your __init__.py includes this router with prefix="/dashboard":
doctor_router = APIRouter() # This will be included with a prefix like /dashboard in __init__.py


# --- Helper Dependency to get current *Doctor* ---
# You need to ensure the authenticated user is a doctor
async def get_current_doctor(current_user: dict = Depends(get_current_authenticated_user)):
    """Dependency to get the current authenticated doctor user document."""
    # get_current_authenticated_user returns the raw user dict or raises 401
    if current_user.get("user_type") != "doctor": # <-- Checks user type from session/DB
        # If authenticated but not a doctor, deny access
        raise HTTPException(status_code=403, detail="Only doctors can access this page.")
    # Return the doctor document dictionary
    return current_user
# --- End Helper Dependency ---


# ---------------------- Doctor's Appointment List Page (GET) ----------------------

@doctor_router.get("/appointments", response_class=HTMLResponse) # This path becomes /dashboard/appointments
async def get_doctor_appointments(
    request: Request,
    current_doctor: dict = Depends(get_current_doctor) # <-- Ensures user is a doctor
):
    """Renders the doctor's appointment list/management page."""
    doctor_id_str = str(current_doctor["_id"]) # Get the doctor's string ObjectId

    try:
        # Fetch appointments for this doctor, sorted by time
        # You might want to filter out old appointments or add more complex sorting (e.g., by severity then time)
        appointments_cursor = db.appointments.find({"doctor_id": doctor_id_str}).sort("appointment_time", 1) # 1 for ascending
        appointments_list_raw = await appointments_cursor.to_list(length=1000) # Fetch appointments

        # --- Fetch Patient Names for Appointments ---
        # For each appointment, fetch the patient's name
        # OPTIMIZATION: For better performance with many appointments, use MongoDB aggregation $lookup
        appointments_with_names = []
        for appointment_doc in appointments_list_raw:
            try:
                # Fetch patient details using their ObjectId string stored in the appointment
                patient_id_str = appointment_doc.get("patient_id")
                patient_doc = None
                if patient_id_str:
                    try:
                        # Convert string ID to ObjectId for the database query
                        patient_doc = await db.patients.find_one({"_id": ObjectId(patient_id_str)})
                    except Exception as e:
                        print(f"Error converting patient_id '{patient_id_str}' to ObjectId for appointment {appointment_doc.get('_id')}: {e}")


                # Add patient name to the appointment dictionary for the template
                if patient_doc:
                     appointment_doc["patient_name"] = f"{patient_doc.get('name', {}).get('first', '')} {patient_doc.get('name', {}).get('last', '')}".strip()
                else:
                     appointment_doc["patient_name"] = "Unknown Patient" # Handle case where patient not found or invalid ID

                appointments_with_names.append(appointment_doc)

            except Exception as patient_fetch_error:
                 print(f"Error fetching patient for appointment {appointment_doc.get('_id')}: {patient_fetch_error}")
                 appointment_doc["patient_name"] = "Error Patient Fetch"
                 appointments_with_names.append(appointment_doc)

        # --- End Fetch Patient Names ---


    except Exception as e:
        print(f"Error fetching doctor's appointments: {e}")
        # Render template with an error message
        return templates.TemplateResponse(
            "doctor_appointments.html",
            {"request": request, "error": "Could not load appointments.", "appointments": [], "doctor": current_doctor}
        )

    # Render the doctor_appointments.html template, passing the list of appointments
    # The HTML will iterate through 'appointments' and display the details
    return templates.TemplateResponse(
        "doctor_appointments.html",
        {"request": request, "appointments": appointments_with_names, "doctor": current_doctor}
    )


# ---------------------- Doctor's "Set Call Link" Action (POST) ----------------------

# This route receives the manually pasted link and updates the DB
@doctor_router.post("/appointments/{appointment_id}/set-call-link") # This path becomes /dashboard/appointments/{id}/set-call-link
async def set_appointment_call_link(
    request: Request,
    appointment_id: str, # Get the appointment ID from the URL path
    gmeet_link: str = Form(...), # Get the link from the form data (sent by JS)
    current_doctor: dict = Depends(get_current_doctor) # <-- Ensures user is a doctor
):
    """Handles the doctor manually setting the call link for an appointment."""
    doctor_id_str = str(current_doctor["_id"])

    try:
        # 1. Find the appointment by ID and ensure it belongs to this doctor
        appointment_oid = ObjectId(appointment_id) # Convert string ID to ObjectId

        # Find the appointment and ensure it belongs to the current doctor
        appointment_doc = await db.appointments.find_one({
            "_id": appointment_oid,
            "doctor_id": doctor_id_str # Crucial security check
        })

        if not appointment_doc:
            raise HTTPException(status_code=404, detail="Appointment not found or does not belong to this doctor.")

        # --- 2. Update Appointment Status and Link ---
        # Set status to 'ReadyForCall' and save the provided link
        # You might add validation here to check if it looks like a valid URL
        update_result = await db.appointments.update_one(
            {"_id": appointment_oid},
            {
                "$set": {
                    "status": "ReadyForCall", # Indicate it's ready for the call
                    "gmeet_link": gmeet_link # Store the manually provided link
                }
            }
        )

        if update_result.modified_count == 0:
             print(f"Warning: Appointment {appointment_id} update modified_count was 0.")
             # Decide how to handle if the document wasn't modified (maybe already Ready or link was the same)

        print(f"Appointment {appointment_id} status updated to ReadyForCall, link set manually.")

        # 3. Return a success response (JSON)
        # The frontend JavaScript expects a JSON response with the link
        return JSONResponse(content={
            "message": "Call link saved and appointment status updated.",
            "gmeet_link": gmeet_link # Return the link back to the frontend
        })

    except HTTPException as he:
         # Re-raise HTTPExceptions (e.g., 403 from dependency, 404 from not found)
         raise he
    except Exception as e:
        # Catch any other unexpected errors during DB operations etc.
        print(f"Error setting call link for {appointment_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set call link: {e}")


# ---------------------- NEW: Doctor's "Mark as Completed" Action (POST) ----------------------

# This route handles marking an appointment as completed
@doctor_router.post("/appointments/{appointment_id}/complete") # <--- NEW ROUTE
async def complete_appointment(
    request: Request,
    appointment_id: str, # Get the appointment ID from the URL path
    current_doctor: dict = Depends(get_current_doctor) # <-- Ensures user is a doctor
):
    """Handles the doctor marking an appointment as completed."""
    doctor_id_str = str(current_doctor["_id"])

    try:
        # 1. Find the appointment by ID and ensure it belongs to this doctor
        appointment_oid = ObjectId(appointment_id) # Convert string ID to ObjectId

        # Find the appointment and ensure it belongs to the current doctor
        appointment_doc = await db.appointments.find_one({
            "_id": appointment_oid,
            "doctor_id": doctor_id_str # Crucial security check
        })

        if not appointment_doc:
            raise HTTPException(status_code=404, detail="Appointment not found or does not belong to this doctor.")

        # --- 2. Update Appointment Status to Completed ---
        update_result = await db.appointments.update_one(
            {"_id": appointment_oid},
            {
                "$set": {
                    "status": "Completed", # Mark the appointment as completed
                    "completed_at": datetime.now(timezone.utc) # Optional: record completion time
                }
            }
        )

        if update_result.modified_count == 0:
             print(f"Warning: Appointment {appointment_id} completion update modified_count was 0.")
             # This might happen if the status was already 'Completed'

        print(f"Appointment {appointment_id} status updated to Completed.")

        # 3. Return a success response (JSON)
        # The frontend JavaScript expects a successful response to remove the card
        return JSONResponse(content={"message": "Appointment marked as completed."})

    except HTTPException as he:
         # Re-raise HTTPExceptions (e.g., 403 from dependency, 404 from not found)
         raise he
    except Exception as e:
        # Catch any other unexpected errors during DB operations etc.
        print(f"Error completing appointment {appointment_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark appointment as completed: {e}")


# Example of including the router in main.py:
# from app.routes import doctor_routes
# app.include_router(doctor_routes.doctor_router, prefix="/dashboard", tags=["Doctor Dashboard"])
