# HEALTHCARE_FINAL/app/routes/home_routes.py

from fastapi import APIRouter, Request
# REMOVE THESE LINES:
# from fastapi.responses import HTMLResponse
# from fastapi.templating import Jinja2Templates
# from pathlib import Path

from app.models.home_page_data_models import HomePageData, Feature, Testimonial # ADD THIS LINE

router = APIRouter()

# REMOVE THIS LINE: templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

# New endpoint for the mobile application to get home page data as JSON
# You can decide to keep the original '/' route for web and add a new '/api/home'
# OR, make '/' return JSON if it's strictly for mobile and you don't need a web version.
# I recommend creating a *new* specific API route for mobile, leaving the old one intact if
# you ever want to serve the web HTML directly from the same backend.
# However, based on your "no render html files" goal, let's replace the existing one.

@router.get("/", response_model=HomePageData, summary="Get Home Page Content for Mobile")
async def get_home_page_data(request: Request):
    """
    Returns structured JSON data for the home page to be consumed by the Flutter frontend.
    This replaces the HTML rendering for the root path.
    """
    # Construct the full URL for static assets if they are hosted on your backend
    # This assumes your FastAPI app is accessible at a base URL (e.g., on Render.com)
    # During local development, it will be http://10.0.2.2:8000/static/logo1.jpg for Android emulator
    # In production, it will be https://your-fastapi-backend-domain.onrender.com/static/logo1.jpg
    
    # You might need to derive the base URL from the request, or use a config variable.
    # For now, let's assume Flutter app knows the base URL and can append '/static/logo1.jpg'
    # Or, if you prefer, you can construct it here:
    # Example for constructing full URL (more robust):
    # base_url = str(request.base_url).rstrip('/') # Get the base URL of the request
    # hero_image_full_url = f"{base_url}/static/logo1.jpg"
    
    # For simplicity in this example, we'll just provide the relative path,
    # and expect the Flutter app to prepend its known backend base URL.
    hero_image_relative_path = "/static/logo1.jpg"

    home_data = HomePageData(
        hero_title="Empower Your Health with Aarogya AI",
        hero_subtitle="Discover personalized health solutions powered by cutting-edge AI to transform your wellness journey.",
        hero_image_url=hero_image_relative_path, # This will be joined with backend URL in Flutter
        
        features_section_title="Why Choose Aarogya AI?",
        features_section_description="Our platform combines advanced technology with compassionate care to deliver unparalleled health solutions.",
        features=[
            Feature(
                icon_name="document",
                title="Personalized Health Plans",
                description="Customized wellness plans tailored to your unique health profile and lifestyle goals."
            ),
            Feature(
                icon_name="lightning",
                title="AI-Powered Insights",
                description="Advanced analytics provide actionable insights to optimize your health journey."
            ),
            Feature(
                icon_name="phone",
                title="24/7 Expert Support",
                description="Round-the-clock access to health professionals for guidance and support."
            ),
        ],
        testimonials_section_title="Voices of Our Community",
        testimonials_section_description="Hear from our users who have transformed their lives with Aarogya AI.",
        testimonials=[
            Testimonial(
                quote="Aarogya AI gave me the tools to take charge of my health like never before. It's a game-changer!",
                author="John Doe",
                role="Satisfied Customer"
            ),
            Testimonial(
                quote="The personalized insights and constant support have made all the difference. Highly recommend!",
                author="Jane Smith",
                role="Happy User"
            ),
        ],
        cta_section_title="Ready to Transform Your Health?",
        cta_section_description="Join thousands of users who are already experiencing the benefits of Aarogya AI's innovative health solutions."
    )
    return home_data

# REMOVE THIS BLOCK (if you don't need the HTML version of the home page anymore):
# @router.get("/", response_class=HTMLResponse)
# async def home(request: Request):
#     return templates.TemplateResponse("home.html", {"request": request})