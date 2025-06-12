from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class Admin(BaseModel):
    username: str
    email: EmailStr
    phone: Optional[str]
    created_at: Optional[datetime] = None
    role: Optional[str] = "admin"
    is_active: bool = True
