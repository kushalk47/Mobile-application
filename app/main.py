# HEALTHCARE_FINAL/app/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
# REMOVE THIS LINE: from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware # ADD THIS LINE
from app.routes import router as api_router

app = FastAPI(
    title="Aarogya AI Backend API", # Optional: Add a title for Swagger UI
    description="Unified Backend API for Aarogya AI Platform (Web & Mobile)", # Optional: Add a description
    version="1.0.0", # Optional: Add a version
)

# Mount static files (KEEP THIS - useful for serving images like your logo)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# REMOVE THIS LINE: app.templates = Jinja2Templates(directory="app/templates")

# ADD CORS Middleware
# Configure origins based on where your Flutter app will run (local development, production)
origins = [
    "http://localhost",
    "http://localhost:3000",        # Common port for Flutter web development
    "http://localhost:8080",        # Default for Flutter web in debug mode
    "http://127.0.0.1:8080",        # Default for Flutter web in debug mode
    "http://10.0.2.2:8000",         # Essential for Android Emulator to access host machine's localhost (your backend)
    "http://192.168.1.X:8000",      # Replace X with your actual local IP if testing on physical device
    # Add your Flutter web app's deployed domain on Render.com (if you deploy Flutter as a web app)
    "https://your-flutter-app-domain.onrender.com",
    # Add the domain where your FastAPI backend is hosted on Render.com
    "https://your-fastapi-backend-domain.onrender.com", # REPLACE WITH YOUR ACTUAL RENDER DOMAIN
    "*" # DANGER! Only use during early development for maximum flexibility. Remove for production.
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers, including Authorization (for JWT)
)

# Include routers from the routes package
app.include_router(api_router) # This includes all routes from app/routes/__init__.py

# Optional: Add a simple root endpoint for a health check or API info
@app.get("/", summary="API Root / Health Check")
async def root():
    return {"message": "Aarogya AI Backend API is running! Access docs at /docs"}