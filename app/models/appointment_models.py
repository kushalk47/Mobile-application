# app/models/appointment_models.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
# Optional: Could define an Enum for clearer severity categories later
# from enum import Enum

# Optional: Define an Enum for severity if desired for stricter validation
# class SeverityCategory(str, Enum):
#     very_serious = "Very Serious"
#     moderate = "Moderate"
#     normal = "Normal"
#     # Add others like 'Unknown' or 'Requires Review' if the analysis can't confidently categorize

class Appointment(BaseModel):
    # Existing fields
    patient_id: str = Field(..., description="Reference to the patient (string ObjectId)")
    doctor_id: str = Field(..., description="Reference to the doctor (string ObjectId)")
    appointment_time: datetime = Field(..., description="Scheduled date and time of the appointment")

    # New field for patient's specific notes/symptoms for this appointment
    patient_notes: Optional[str] = Field(None, description="Patient's description of symptoms or concerns for this appointment")

    reason: Optional[str] = Field(None, description="General reason for the appointment")

    # Modified status field to include states related to the call
    # Expanded status options: Scheduled, ReadyForCall, InCall, Completed, Cancelled, etc.
    status: str = Field(default="Scheduled", description="Appointment status: Scheduled, ReadyForCall, InCall, Completed, Cancelled, etc.")

    # New field to store the Google Meet or other video call link
    gmeet_link: Optional[str] = Field(None, description="Google Meet or other video call link for the appointment")

    # --- NEW FIELD FOR PREDICTED SEVERITY ---
    # Stores the result from the Gemini analysis for prioritization
    # Using str for simplicity, could use Optional[SeverityCategory] if Enum is defined above
    predicted_severity: Optional[str] = Field(
        None,
        description="Predicted severity category (e.g., 'Very Serious', 'Moderate', 'Normal') based on analysis of reason/notes"
    )
    # ----------------------------------------

    # Existing fields
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Appointment creation timestamp")

    # --- Optional: Add config for ORM mode if you map to MongoDB directly ---
    # class Config:
    #     orm_mode = True
    #     json_encoders = {
    #         ObjectId: str
    #     }
    #     arbitrary_types_allowed = True
    # --- End Optional ---