# app/models/request_models.py (example file name)

from pydantic import BaseModel, Field
from typing import Optional

class ChatRequest(BaseModel):
    """Request body for the chatbot endpoint."""
    query: Optional[str] = Field(None, description="Text query from the user.")
    action: str = Field('ask', description="Action to perform: 'ask' or 'summarize'. Defaults to 'ask'.")

class ReportRequest(BaseModel):
    """Request body for the AI report text generation endpoint."""
    transcribed_text: str = Field(..., description="Raw transcribed text to be formatted by AI.")

class ReportPDFRequest(BaseModel):
    """Request body for the PDF report generation endpoint."""
    report_content_text: str = Field(..., description="Formatted report text (potentially edited by the user) to be converted to PDF.")

# You might also put other API-specific response models here if you have them.