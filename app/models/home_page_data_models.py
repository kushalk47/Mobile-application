# HEALTHCARE_FINAL/app/models/home_page_data_models.py

from pydantic import BaseModel
from typing import List, Optional

class Feature(BaseModel):
    icon_name: str
    title: str
    description: str

class Testimonial(BaseModel):
    quote: str
    author: str
    role: str

class HomePageData(BaseModel):
    hero_title: str
    hero_subtitle: str
    hero_image_url: Optional[str] = None

    features_section_title: str
    features_section_description: str
    features: List[Feature]

    testimonials_section_title: str
    testimonials_section_description: str
    testimonials: List[Testimonial]

    cta_section_title: str
    cta_section_description: str