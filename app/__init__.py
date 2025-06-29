from fastapi import APIRouter

from app.routes.auth_routes import  auth_router
from app.routes.home_routes import router as home_router
from app.routes.profile  import  profile_router
#from app.routes.doctor_routes import doctor_router
from app.routes.appointment_route import appointment_router
#from app.routes.doctor_appointment_routes import doctor_router as doctor_appointment_router
from app.routes.patient_routes import patient_router
#from app.routes.patient_routes import router as patient_router
#from app.routes.doctor_routes import router as doctor_router
#from app.routes.appointment_routes import router as appointment_router
#from app.routes.medical_records_routes import router as medical_records_router

router = APIRouter()

#Include all route modules
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(home_router, prefix="", tags=["Home"])  # For base "/"
router.include_router(profile_router, prefix="/profile", tags=["profile"])
#router.include_router(doctor_router,prefix="",tags=["dashboard"])
router.include_router(appointment_router, prefix="/appointments", tags=["Appointments"])
#router.include_router(doctor_appointment_router, prefix="/dashboard", tags=["Doctor Appointments"])
router.include_router(patient_router, prefix="/patient", tags=["Patient"])
#router.include_router(patient_router, prefix="/patient", tags=["Patient"])
#router.include_router(doctor_router, prefix="/doctor", tags=["Doctor"])
#router.include_router(appointment_router, prefix="/appointments", tags=["Appointments"])
#router.include_router(medical_records_router, prefix="/medical-records", tags=["Medical Records"])
