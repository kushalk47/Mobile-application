from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Name(BaseModel):
    first: str
    middle: Optional[str] = None
    last: str

class Education(BaseModel):
    degree: str
    institution: str
    graduation_year: int

class Certification(BaseModel):
    name: str
    issued_by: str
    date_issued: datetime
    expiry_date: Optional[datetime] = None

class ScheduleSlot(BaseModel):
    day: str  # e.g., "Monday"
    start_time: str  # e.g., "09:00"
    end_time: str  # e.g., "13:00"

class DoctorCreate(BaseModel):
    name: Name
    specialization: str
    email: str
    phone: str
    department: str
    years_of_experience: int
    education: List[Education]
    certifications: List[Certification]
    schedule: List[ScheduleSlot]
    languages_spoken: List[str] = []
    biography: Optional[str] = None

class DoctorLogin(BaseModel):
    email: str
    password: str

class Doctor(DoctorCreate):
    id: str  # This will be used when returning doctor data from the database
    registration_date: datetime
