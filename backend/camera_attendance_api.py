import sys
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ============================================================
# PATH SETUP
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"

# deep_face_attendance.py uses:
# from excel_export import export_database_to_excel
# So make sure the backend folder is available to Python.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ============================================================
# IMPORT EXISTING ATTENDANCE SYSTEM
# ============================================================

import deep_face_attendance as attendance


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="BEL Workforce Camera Attendance API",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# CAMERA LOCK
# ============================================================

# Only one employee can use the webcam attendance process
# at a time.
camera_lock = threading.Lock()


# ============================================================
# REQUEST MODEL
# ============================================================

class AttendanceRequest(BaseModel):
    employee_id: str
    action: str


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "BEL Workforce Camera Attendance API is running",
        "status": "OK"
    }


# ============================================================
# CHECK TODAY'S ATTENDANCE
# ============================================================

@app.get("/api/camera-attendance/status/{employee_id}")
def attendance_status(employee_id: str):

    employee_id = employee_id.strip().upper()

    attendance_record = attendance.get_today_attendance(
        employee_id
    )

    if attendance_record is None:
        return {
            "employee_id": employee_id,
            "status": "NOT_CHECKED_IN",
            "check_in": None,
            "check_out": None,
            "working_hours": 0
        }

    return {
        "employee_id": employee_id,
        "status": (
            "CHECKED_OUT"
            if attendance_record["check_out"]
            else "CHECKED_IN"
        ),
        "check_in": attendance_record["check_in"],
        "check_out": attendance_record["check_out"],
        "working_hours": (
            attendance_record["working_hours"] or 0
        )
    }


# ============================================================
# RUN CAMERA ATTENDANCE
# ============================================================

@app.post("/api/camera-attendance/scan")
def camera_attendance(request: AttendanceRequest):

    employee_id = request.employee_id.strip().upper()
    action = request.action.strip().lower()

    if action not in ["check_in", "check_out"]:
        raise HTTPException(
            status_code=400,
            detail="Action must be check_in or check_out."
        )

    # --------------------------------------------------------
    # Verify employee exists
    # --------------------------------------------------------

    employees = attendance.get_employees()

    employee = None

    for item in employees:
        if str(item["employee_id"]).upper() == employee_id:
            employee = item
            break

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Employee not found."
        )

    # --------------------------------------------------------
    # Check current attendance state BEFORE opening camera
    # --------------------------------------------------------

    existing = attendance.get_today_attendance(
        employee_id
    )

    if action == "check_in":

        if existing is not None and existing["check_in"]:
            raise HTTPException(
                status_code=400,
                detail="You are already checked in today."
            )

    if action == "check_out":

        if existing is None or not existing["check_in"]:
            raise HTTPException(
                status_code=400,
                detail="Check-out is not available because check-in was not found."
            )

        if existing["check_out"]:
            raise HTTPException(
                status_code=400,
                detail="You are already checked out today."
            )

    # --------------------------------------------------------
    # Prevent two camera sessions at the same time
    # --------------------------------------------------------

    if not camera_lock.acquire(blocking=False):

        raise HTTPException(
            status_code=409,
            detail="Camera attendance is already being used. Please wait."
        )

    camera = None
    landmarker = None

    try:

        print()
        print("=" * 70)
        print("WEBSITE CAMERA ATTENDANCE")
        print(f"Employee requesting attendance: {employee_id}")
        print(f"Requested action: {action}")
        print("=" * 70)

        # ----------------------------------------------------
        # Voice system
        # ----------------------------------------------------

        voice_engine = attendance.create_voice_engine()

        # ----------------------------------------------------
        # Load employee face embeddings
        # ----------------------------------------------------

        employee_embeddings = (
            attendance.load_employee_embeddings()
        )

        if not employee_embeddings:

            raise HTTPException(
                status_code=500,
                detail="No registered face embeddings were found."
            )

        # ----------------------------------------------------
        # Check requested employee has face data
        # ----------------------------------------------------

        if employee_id not in employee_embeddings:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"No face embedding found for {employee_id}. "
                    "Please register your face first."
                )
            )

        # ----------------------------------------------------
        # Check MediaPipe model
        # ----------------------------------------------------

        if not attendance.LANDMARKER_MODEL.exists():

            raise HTTPException(
                status_code=500,
                detail="Liveness model was not found."
            )

        # ----------------------------------------------------
        # Initialize InsightFace
        # ----------------------------------------------------

        print("Loading InsightFace...")

        face_app = attendance.FaceAnalysis(
            name="buffalo_l",
            providers=[
                "CPUExecutionProvider"
            ]
        )

        face_app.prepare(
            ctx_id=0,
            det_size=(640, 640)
        )

        print("InsightFace loaded successfully.")

        # ----------------------------------------------------
        # Initialize MediaPipe
        # ----------------------------------------------------

        print("Loading MediaPipe liveness model...")

        base_options = attendance.python.BaseOptions(
            model_asset_path=str(
                attendance.LANDMARKER_MODEL
            )
        )

        options = attendance.vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=attendance.vision.RunningMode.IMAGE,
            num_faces=5,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )

        landmarker = (
            attendance.vision.FaceLandmarker
            .create_from_options(options)
        )

        print(
            "MediaPipe liveness model loaded successfully."
        )

        # ----------------------------------------------------
        # Open webcam
        # ----------------------------------------------------

        print("Opening camera...")

        camera = attendance.cv2.VideoCapture(0)

        if not camera.isOpened():

            raise HTTPException(
                status_code=500,
                detail="Could not open webcam."
            )

        camera.set(
            attendance.cv2.CAP_PROP_FRAME_WIDTH,
            1280
        )

        camera.set(
            attendance.cv2.CAP_PROP_FRAME_HEIGHT,
            720
        )

        print("Camera opened successfully.")

        # ====================================================
        # STAGE 1
        # LIVENESS
        # ====================================================

        liveness_verified = attendance.verify_liveness(
            camera,
            landmarker,
            voice_engine
        )

        if not liveness_verified:

            return {
                "success": False,
                "employee_id": employee_id,
                "message": "Liveness verification failed."
            }

        # ====================================================
        # STAGE 2
        # FACE RECOGNITION
        # ====================================================

        print("Starting face recognition...")

        # The existing recognition function performs:
        #
        # 1. Face detection
        # 2. Unknown-face rejection
        # 3. Similarity calculation
        # 4. 5 consecutive confirmations
        # 5. Attendance database update
        #
        # We keep that logic unchanged.

        result = attendance.recognition_phase(
            camera,
            face_app,
            employee_embeddings,
            voice_engine
        )

        # ----------------------------------------------------
        # IMPORTANT EMPLOYEE VERIFICATION
        # ----------------------------------------------------

        # The existing recognition_phase() returns only True/False.
        #
        # Therefore, after the recognition process we check
        # today's database record for the logged-in employee.
        #
        # The frontend will refresh the dashboard afterwards.

        updated_record = attendance.get_today_attendance(
            employee_id
        )

        if updated_record is None:

            return {
                "success": False,
                "employee_id": employee_id,
                "message": (
                    "Face recognition completed, "
                    "but attendance was not marked."
                )
            }

        # ----------------------------------------------------
        # Verify requested action
        # ----------------------------------------------------

        if action == "check_in":

            if not updated_record["check_in"]:

                return {
                    "success": False,
                    "employee_id": employee_id,
                    "message": "Check-in was not marked."
                }

            return {
                "success": True,
                "employee_id": employee_id,
                "name": employee["name"],
                "action": "check_in",
                "check_in": updated_record["check_in"],
                "check_out": updated_record["check_out"],
                "working_hours": (
                    updated_record["working_hours"] or 0
                ),
                "message": "Check-in completed successfully."
            }

        # ----------------------------------------------------
        # CHECK-OUT
        # ----------------------------------------------------

        if action == "check_out":

            if not updated_record["check_out"]:

                return {
                    "success": False,
                    "employee_id": employee_id,
                    "message": "Check-out was not marked."
                }

            return {
                "success": True,
                "employee_id": employee_id,
                "name": employee["name"],
                "action": "check_out",
                "check_in": updated_record["check_in"],
                "check_out": updated_record["check_out"],
                "working_hours": (
                    updated_record["working_hours"] or 0
                ),
                "message": "Check-out completed successfully."
            }

        return {
            "success": bool(result),
            "employee_id": employee_id,
            "message": "Attendance process completed."
        }

    except HTTPException:
        raise

    except Exception as error:

        print()
        print("=" * 70)
        print("CAMERA ATTENDANCE ERROR")
        print(error)
        print("=" * 70)

        return {
            "success": False,
            "employee_id": employee_id,
            "message": (
                "Camera attendance failed. "
                "Please try again."
            ),
            "error": str(error)
        }

    finally:

        # ----------------------------------------------------
        # CAMERA CLEANUP
        # ----------------------------------------------------

        if camera is not None:

            try:
                camera.release()
            except Exception:
                pass

        try:
            attendance.cv2.destroyAllWindows()
        except Exception:
            pass

        # ----------------------------------------------------
        # MEDIAPIPE CLEANUP
        # ----------------------------------------------------

        if landmarker is not None:

            try:
                landmarker.close()
            except Exception:
                pass

        # ----------------------------------------------------
        # RELEASE CAMERA LOCK
        # ----------------------------------------------------

        camera_lock.release()