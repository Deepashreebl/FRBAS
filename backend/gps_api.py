from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.location_service import verify_bel_location


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Smart Attendance GPS Service",
    description="BEL Bengaluru campus geofence verification",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class LocationRequest(BaseModel):

    latitude: float
    longitude: float
    accuracy: float | None = None


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "system": "Smart Attendance GPS Service",
        "status": "running",
        "purpose": "BEL Bengaluru campus location verification"
    }


# ============================================================
# LOCATION VERIFICATION
# ============================================================

@app.post("/api/location/verify")
def verify_location(request: LocationRequest):

    result = verify_bel_location(
        request.latitude,
        request.longitude
    )

    result["gps_accuracy"] = request.accuracy

    return result


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/location/health")
def health_check():

    return {
        "status": "healthy",
        "service": "GPS Geofence"
    }