# app/models/patient_models.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId # Import ObjectId for type hinting if needed


# --- API Request Models (Add these to your file) ---
class ChatRequest(BaseModel):
    """Request body for the chatbot endpoint."""
    query: Optional[str] = Field(None, description="Text query from the user.")
    action: str = Field('ask', description="Action to perform: 'ask' or 'summarize'. Defaults to 'ask'.")

class ReportRequest(BaseModel):
    """Request body for the AI report text generation endpoint.
       Also used by the PDF generation endpoint in your current setup (expecting raw text)."""
    transcribed_text: str = Field(..., description="Raw transcribed text to be formatted by AI.")

class ReportPDFRequest(BaseModel):
    """Request body for the PDF report generation endpoint
       (if it were designed to accept pre-formatted text)."""
    report_content_text: str = Field(..., description="Formatted report text (potentially edited by the user) to be converted to PDF.")
# --- End API Request Models ---


# ---------------------- Patient Details ----------------------

class Name(BaseModel):
    first: str
    middle: Optional[str] = None
    last: str

class Address(BaseModel):
    street: str
    city: str
    state: str
    zip: str
    country: str

class EmergencyContact(BaseModel):
    name: str
    phone: str
    relationship: str

class PatientCreate(BaseModel):
    name: Name
    email: str
    phone_number: str
    password: str
    age: int
    gender: str
    address: Address
    emergency_contact: EmergencyContact
    # Add date_of_birth if it's part of creation, it's needed for PDF
    date_of_birth: Optional[str] = None # Or datetime


class PatientLogin(BaseModel):
    email: str
    password: str

class Patient(PatientCreate):
    # Use Pydantic's AliasPath for MongoDB's _id and map it to 'id'
    # Or handle the _id -> id conversion explicitly in your DB fetching code
    # For simplicity in models, if you just need a string ID:
    id: str = Field(..., alias='_id') # Map _id from DB to 'id' in Pydantic model
    registration_date: datetime

    # Enable orm_mode to allow Pydantic to work with ORM objects or dicts with aliases
    class Config:
        populate_by_name = True # Allow field population by name (like 'id') even if alias is set
        json_encoders = {ObjectId: str} # Optional: Configure JSON encoding for ObjectId if returning Pydantic objects directly
        arbitrary_types_allowed = True # Needed if using ObjectId in models without custom serialization

# ---------------------- Medical Records ----------------------

class Medication(BaseModel):
    name: str
    dosage: str
    frequency: str
    start_date: datetime
    end_date: Optional[datetime] = None
    notes: Optional[str] = None

class Diagnosis(BaseModel):
    disease: str
    year: int
    diagnosis_date: datetime
    notes: Optional[str] = None

class Prescription(BaseModel):
    doctor_id: str # Assuming this is a string representation of Doctor ObjectId
    medication: str
    dosage: str
    frequency: str
    date: datetime
    refillable: bool
    refill_count: int
    notes: Optional[str] = None

class Consultation(BaseModel):
    appointment_id: str # Assuming this is a string ID
    doctor_id: str # Assuming this is a string representation of Doctor ObjectId
    date: datetime
    notes: Optional[str] = None
    diagnosis: Optional[str] = None
    followup_date: Optional[datetime] = None

# --- Report Model (Used within MedicalRecord) ---
class Report(BaseModel):
    report_id: str # Unique identifier for the report itself (e.g., UUID or string ObjectId if stored separately)
    report_type: str # e.g., "AI Generated Consultation", "Lab Result"
    date: datetime
    # Reference to the actual content stored elsewhere
    content_id: str # String ObjectId of the document in report_contents collection
    # summary: Optional[str] = None # Optional summary field

# --- New Model for Report Content (Stored in a separate collection) ---
class ReportContent(BaseModel):
    # MongoDB will add _id automatically. Pydantic doesn't strictly need it defined
    # unless you're fetching INTO this model and need validation.
    # content_id: str = Field(..., alias='_id') # Map _id from DB if fetching into this model
    content: str # The actual long text of the report

    # class Config:
    #     populate_by_name = True
    #     json_encoders = {ObjectId: str}
    #     arbitrary_types_allowed = True


class Immunization(BaseModel):
    vaccine: str
    date: datetime
    lot_number: Optional[str] = None
    administered_by: str # Assuming this is a string name or ID

class MedicalRecord(BaseModel):
    # MedicalRecord likely stored per patient. patient_id is the link.
    # We don't need an explicit _id field here for Pydantic model definition
    # unless you're fetching into this model and need validation/aliasing.
    # id: str = Field(..., alias='_id') # Uncomment if you fetch MedicalRecord docs directly
    patient_id: str # String representation of Patient ObjectId
    current_medications: List[Medication] = []
    diagnoses: List[Diagnosis] = []
    prescriptions: List[Prescription] = []
    consultation_history: List[Consultation] = []
    reports: List[Report] = [] # This list now contains Report objects with content_id
    allergies: List[str] = []
    immunizations: List[Immunization] = []
    family_medical_history: Optional[str] = None

    # class Config:
    #     populate_by_name = True
    #     json_encoders = {ObjectId: str}
    #     arbitrary_types_allowed = True


# If you need to explicitly import these into app.models.__init__.py
# for `from app.models import ...` to work, ensure your __init__.py
# has lines like:
# from .patient_models import ChatRequest, ReportRequest, ReportPDFRequest, Patient, MedicalRecord, etc.