import os

import re

import secrets

from datetime import datetime

from pathlib import Path



import cv2

import numpy as np

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from fastapi import (

    FastAPI,

    HTTPException,

    UploadFile,

    File,

    Request,

    Depends,

    Form,

)

from fastapi.responses import FileResponse, Response

from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from starlette.middleware.sessions import SessionMiddleware

from pwdlib import PasswordHash



from backend.db import (

    Base,

    engine,

    SessionLocal,

    Employee,

    User,

    Attendance,

)

from backend.storage import upload_image, download_image





# ---------------- CONFIGURATION ----------------



ROOT = Path(__file__).resolve().parent.parent

FRONTEND = ROOT / "frontend"

FACES = ROOT / "face_data"

ATTENDANCE_PHOTOS = ROOT / "attendance_photos"



FACES.mkdir(parents=True, exist_ok=True)

ATTENDANCE_PHOTOS.mkdir(parents=True, exist_ok=True)



Base.metadata.create_all(bind=engine)



app = FastAPI(title="BEL WORKFORCE")



SESSION_SECRET = os.getenv(

    "SESSION_SECRET",

    "local-development-only-change-this",

)



app.add_middleware(

    SessionMiddleware,

    secret_key=SESSION_SECRET,

    same_site="lax",

    https_only=(

        os.getenv("COOKIE_HTTPS_ONLY", "false").lower() == "true"

    ),

)



app.mount(

    "/static",

    StaticFiles(directory=str(FRONTEND)),

    name="static",

)



passwords = PasswordHash.recommended()





# ---------------- INITIAL ADMIN ACCOUNT ----------------



with SessionLocal() as db:

    admin_username = os.getenv("ADMIN_USERNAME")

    admin_password = os.getenv("ADMIN_PASSWORD")



    if admin_username and admin_password:

        existing_admin = (

            db.query(User)

            .filter_by(username=admin_username)

            .first()

        )



        if not existing_admin:

            db.add(

                User(

                    username=admin_username,

                    password_hash=passwords.hash(admin_password),

                    role="admin",

                )

            )

            db.commit()





# ---------------- REQUEST MODELS ----------------



class Login(BaseModel):

    username: str

    password: str





class AdminSignup(BaseModel):

    setup_key: str

    username: str

    password: str





class EmployeeInput(BaseModel):

    employee_id: str

    name: str

    department: str

    password: str





class EmployeeUpdate(BaseModel):

    employee_id: str

    name: str

    department: str

    password: str = ""





# ---------------- AUTHENTICATION ----------------



def current_user(request: Request):

    """Validate the session against the database on each request."""

    uid = request.session.get("uid")



    if not uid:

        raise HTTPException(401, "Please log in.")



    with SessionLocal() as db:

        user = db.get(User, uid)



        if not user:

            request.session.clear()

            raise HTTPException(

                401,

                "Invalid session. Please log in again.",

            )



        return {

            "id": user.id,

            "role": user.role,

            "employee_pk": user.employee_pk,

        }





def require_admin(request: Request):

    user = current_user(request)



    if user["role"] != "admin":

        raise HTTPException(

            403,

            "Administrator access required.",

        )



    return user





# ---------------- FACE DETECTOR ----------------



def face_detector():

    cascade_name = "haarcascade_frontalface_default.xml"



    possible_paths = [

        Path(cv2.data.haarcascades) / cascade_name,

        ROOT / cascade_name,

        ROOT / "backend" / cascade_name,

    ]



    for cascade_path in possible_paths:

        if not cascade_path.is_file():

            continue



        detector = cv2.CascadeClassifier(str(cascade_path))



        if not detector.empty():

            return detector



    checked_paths = "\n".join(str(path) for path in possible_paths)



    raise HTTPException(

        status_code=500,

        detail=(

            "Face detector could not be loaded. "

            "The Haar cascade XML file is missing or invalid. "

            f"Checked paths:\n{checked_paths}"

        ),

    )





# ---------------- PAGES ----------------



@app.get("/")

def home():

    return FileResponse(FRONTEND / "index.html")





@app.get("/admin")

def admin_page():

    return FileResponse(FRONTEND / "admin.html")





@app.get("/admin-signup")

def admin_signup_page():

    return FileResponse(FRONTEND / "admin_signup.html")





@app.get("/employee")

def employee_page():

    return FileResponse(FRONTEND / "employee.html")





@app.get("/check-in")

@app.get("/check-out")

def scanner_page():

    return FileResponse(FRONTEND / "scanner.html")





# ---------------- HEALTH CHECK ----------------



@app.get("/api/health")

def health():

    return {

        "status": "running",

        "application": "BEL WORKFORCE",

    }





# ---------------- ADMIN SIGN-UP ----------------



@app.post("/api/admin/signup")

def admin_signup(data: AdminSignup):

    expected_key = os.getenv("ADMIN_SIGNUP_KEY")



    if not expected_key:

        raise HTTPException(

            503,

            "Admin sign-up is disabled. Configure ADMIN_SIGNUP_KEY.",

        )



    if not secrets.compare_digest(data.setup_key, expected_key):

        raise HTTPException(403, "Invalid setup key.")



    username = data.username.strip()



    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", username):

        raise HTTPException(

            400,

            "Username must be 3-80 characters and use letters, "

            "numbers, _, . or -.",

        )



    if len(data.password) < 8:

        raise HTTPException(

            400,

            "Administrator password must contain at least 8 characters.",

        )



    with SessionLocal() as db:

        if db.query(User).filter_by(role="admin").first():

            raise HTTPException(

                409,

                "An administrator already exists. Sign-up is closed.",

            )



        if db.query(User).filter_by(username=username).first():

            raise HTTPException(409, "Username already exists.")



        db.add(

            User(

                username=username,

                password_hash=passwords.hash(data.password),

                role="admin",

            )

        )

        db.commit()



    return {

        "message": "Administrator account created successfully."

    }





# ---------------- LOGIN ----------------



@app.post("/api/login")

def login(data: Login, request: Request):

    with SessionLocal() as db:

        user = (

            db.query(User)

            .filter_by(username=data.username.strip())

            .first()

        )



        if not user or not passwords.verify(

            data.password,

            user.password_hash,

        ):

            raise HTTPException(

                401,

                "Invalid username or password.",

            )



        request.session.clear()

        request.session["uid"] = user.id



        return {

            "message": "Login successful",

            "role": user.role,

        }





@app.post("/api/logout")

def logout(request: Request):

    request.session.clear()

    return {"message": "Logged out"}





@app.get("/api/me")

def me(user=Depends(current_user)):

    return {

        "role": user["role"],

        "employee_pk": user["employee_pk"],

    }





# ---------------- REGISTER EMPLOYEE ----------------



@app.post("/api/employees")

def add_employee(

    data: EmployeeInput,

    user=Depends(require_admin),

):

    employee_id = data.employee_id.strip()

    name = data.name.strip()

    department = data.department.strip()

    permanent_password = data.password



    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", employee_id):

        raise HTTPException(400, "Invalid employee ID.")



    if not name or len(name) > 120:

        raise HTTPException(400, "Enter a valid employee name.")



    if not department or len(department) > 100:

        raise HTTPException(400, "Enter a valid department.")



    if len(permanent_password) < 6:

        raise HTTPException(

            400,

            "Employee password must contain at least 6 characters.",

        )



    with SessionLocal() as db:

        if db.query(Employee).filter_by(

            employee_id=employee_id

        ).first():

            raise HTTPException(409, "Employee ID already exists.")



        if db.query(User).filter_by(

            username=employee_id

        ).first():

            raise HTTPException(409, "Username already exists.")



        employee = Employee(

            employee_id=employee_id,

            name=name,

            department=department,

        )



        db.add(employee)

        db.flush()



        employee_user = User(

            username=employee_id,

            password_hash=passwords.hash(permanent_password),

            role="employee",

            employee_pk=employee.id,

        )



        db.add(employee_user)

        db.commit()



        return {

            "message": "Employee registered successfully.",

            "employee_id": employee_id,

            "username": employee_id,

        }





# ---------------- LIST EMPLOYEES ----------------



@app.get("/api/employees")

def list_employees(user=Depends(require_admin)):

    with SessionLocal() as db:

        employees = (

            db.query(Employee)

            .order_by(Employee.employee_id)

            .all()

        )



        return [

            {

                "employee_id": employee.employee_id,

                "name": employee.name,

                "department": employee.department,

                "photo_enrolled": bool(employee.face_data),

            }

            for employee in employees

        ]





# ---------------- EDIT EMPLOYEE ----------------



@app.put("/api/employees/{employee_id}")

def edit_employee(

    employee_id: str,

    data: EmployeeUpdate,

    user=Depends(require_admin),

):

    """Update employee details and, optionally, the linked password."""

    old_employee_id = employee_id.strip()

    new_employee_id = data.employee_id.strip()

    name = data.name.strip()

    department = data.department.strip()

    new_password = data.password or ""



    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", new_employee_id):

        raise HTTPException(400, "Invalid employee ID.")



    if not name or len(name) > 120:

        raise HTTPException(

            400,

            "Enter a valid employee name (maximum 120 characters).",

        )



    if not department or len(department) > 100:

        raise HTTPException(

            400,

            "Enter a valid department (maximum 100 characters).",

        )



    if new_password and len(new_password) < 6:

        raise HTTPException(

            400,

            "Employee password must contain at least 6 characters.",

        )



    with SessionLocal() as db:

        employee = (

            db.query(Employee)

            .filter_by(employee_id=old_employee_id)

            .first()

        )



        if not employee:

            raise HTTPException(404, "Employee not found.")



        duplicate_employee = (

            db.query(Employee)

            .filter(

                Employee.employee_id == new_employee_id,

                Employee.id != employee.id,

            )

            .first()

        )



        if duplicate_employee:

            raise HTTPException(

                409,

                "That employee ID is already assigned to another employee.",

            )



        employee_user = (

            db.query(User)

            .filter(

                User.role == "employee",

                User.employee_pk == employee.id,

            )

            .first()

        )



        # Support older accounts without employee_pk.

        if not employee_user:

            employee_user = (

                db.query(User)

                .filter_by(

                    username=old_employee_id,

                    role="employee",

                )

                .first()

            )



        duplicate_user = (

            db.query(User)

            .filter(User.username == new_employee_id)

            .first()

        )



        if duplicate_user and (

            employee_user is None

            or duplicate_user.id != employee_user.id

        ):

            raise HTTPException(

                409,

                "That employee ID is already being used as a login username.",

            )



        try:

            employee.employee_id = new_employee_id

            employee.name = name

            employee.department = department



            if employee_user:

                employee_user.username = new_employee_id



                if new_password:

                    employee_user.password_hash = passwords.hash(

                        new_password

                    )



            elif new_password:

                db.add(

                    User(

                        username=new_employee_id,

                        password_hash=passwords.hash(new_password),

                        role="employee",

                        employee_pk=employee.id,

                    )

                )



            db.commit()

            db.refresh(employee)



        except Exception:

            db.rollback()

            raise HTTPException(

                500,

                "Employee update failed. No changes were saved.",

            )



        return {

            "message": "Employee details updated successfully.",

            "employee_id": employee.employee_id,

            "name": employee.name,

            "department": employee.department,

            "password_changed": bool(new_password),

        }





# ---------------- DELETE EMPLOYEE ----------------



@app.delete("/api/employees/{employee_id}")

def delete_employee(

    employee_id: str,

    user=Depends(require_admin),

):

    """Delete an employee, linked login, attendance, and face image."""

    face_file_to_remove = None



    with SessionLocal() as db:

        employee = (

            db.query(Employee)

            .filter_by(employee_id=employee_id)

            .first()

        )



        if not employee:

            raise HTTPException(404, "Employee not found.")



        employee_pk = employee.id

        employee_login = employee.employee_id



        if employee.face_data:

            try:

                candidate = Path(employee.face_data).resolve()

                allowed_directory = FACES.resolve()



                if candidate.parent == allowed_directory:

                    face_file_to_remove = candidate



            except (OSError, RuntimeError):

                face_file_to_remove = None



        try:

            db.query(Attendance).filter(

                Attendance.employee_id == employee_pk

            ).delete(synchronize_session=False)



            db.query(User).filter(

                User.role == "employee",

                (

                    (User.employee_pk == employee_pk)

                    | (User.username == employee_login)

                ),

            ).delete(synchronize_session=False)



            db.delete(employee)

            db.commit()



        except Exception:

            db.rollback()

            raise HTTPException(

                500,

                "Employee deletion failed. Database changes were rolled back.",

            )



    cleanup_warning = None



    if face_file_to_remove is not None:

        try:

            face_file_to_remove.unlink(missing_ok=True)

        except OSError:

            cleanup_warning = (

                "The employee and database records were deleted, "

                "but the face image could not be removed automatically. "

                "Check the face_data directory."

            )



    return {

        "message": "Employee and associated database records deleted.",

        "employee_id": employee_login,

        "deleted": True,

        "face_file_cleanup_warning": cleanup_warning,

    }





# ---------------- ENROLL EMPLOYEE PHOTO ----------------



@app.post("/api/employees/{employee_id}/face")

async def enroll_face(

    employee_id: str,

    photo: UploadFile = File(...),

    user=Depends(require_admin),

):

    if photo.content_type not in ("image/jpeg", "image/png"):

        raise HTTPException(400, "Upload a JPG or PNG image.")



    raw = await photo.read()



    if not raw or len(raw) > 5_000_000:

        raise HTTPException(400, "Image must be under 5 MB.")



    image = cv2.imdecode(

        np.frombuffer(raw, dtype=np.uint8),

        cv2.IMREAD_GRAYSCALE,

    )



    if image is None:

        raise HTTPException(400, "Invalid image.")



    faces = face_detector().detectMultiScale(

        image,

        scaleFactor=1.2,

        minNeighbors=5,

        minSize=(80, 80),

    )



    if len(faces) != 1:

        raise HTTPException(

            400,

            "Use a clear photo with exactly one face.",

        )



    x, y, w, h = faces[0]



    face = cv2.resize(

        image[y:y + h, x:x + w],

        (200, 200),

    )



    with SessionLocal() as db:

        employee = (

            db.query(Employee)

            .filter_by(employee_id=employee_id)

            .first()

        )



        if not employee:

            raise HTTPException(404, "Employee not found.")



        success, encoded = cv2.imencode(".jpg", face)

        if not success:
           raise HTTPException(500, "Could not encode employee photo.")

        object_key = f"faces/{employee.id}.jpg"

        try:
           upload_image(object_key, encoded.tobytes())
        except Exception:
            raise HTTPException(
              500,
              "Could not upload employee photo to storage.",
            )

        employee.face_data = object_key
        db.commit()






    return {"message": "Employee photo enrolled."}





# ---------------- FACE MATCHING AND ATTENDANCE ----------------



@app.post("/api/scan")

async def scan_employee(

    mode: str = Form(...),

    photo: UploadFile = File(...),
):

    if mode not in ("check-in", "check-out"):

        raise HTTPException(400, "Invalid attendance mode.")



    if photo.content_type not in ("image/jpeg", "image/png"):

        raise HTTPException(400, "Invalid camera image.")



    raw = await photo.read()



    if not raw or len(raw) > 5_000_000:

        raise HTTPException(

            400,

            "Camera image is empty or too large.",

        )



    frame = cv2.imdecode(

        np.frombuffer(raw, dtype=np.uint8),

        cv2.IMREAD_GRAYSCALE,

    )



    if frame is None:

        raise HTTPException(400, "Could not read camera image.")



    faces = face_detector().detectMultiScale(

        frame,

        scaleFactor=1.2,

        minNeighbors=5,

        minSize=(80, 80),

    )



    if len(faces) == 0:

        return {

            "status": "no_face",

            "message": "No face detected.",

        }



    if len(faces) != 1:

        return {

            "status": "multiple_faces",

            "message": "Only one person should face the camera.",

        }



    x, y, w, h = faces[0]



    query_face = cv2.resize(

        frame[y:y + h, x:x + w],

        (200, 200),

    )



    if not hasattr(cv2, "face"):

        raise HTTPException(

            500,

            "OpenCV contrib face module is missing. "

            "Install opencv-contrib-python-headless.",

        )



    recognizer = cv2.face.LBPHFaceRecognizer_create()



    training_images = []

    labels = []

    employee_names = {}



    with SessionLocal() as db:

        employees = db.query(Employee).all()



        for employee in employees:

            if not employee.face_data:

                continue



            try:
              if employee.face_data.startswith("faces/"):
                image_bytes = download_image(employee.face_data)

                enrolled_face = cv2.imdecode(
                  np.frombuffer(image_bytes, dtype=np.uint8),
                  cv2.IMREAD_GRAYSCALE,
                )
              else:
                 # Support existing local image paths where available.
                 saved_path = Path(employee.face_data)

                 if not saved_path.is_file():
                   continue

                 enrolled_face = cv2.imread(
                   str(saved_path),
                    cv2.IMREAD_GRAYSCALE,
                )

            except Exception as exc:
                print(
                   f"FACE STORAGE ERROR | employee={employee.employee_id} "
                   f"| {type(exc).__name__}: {exc}"
                )
                continue

            if enrolled_face is None:
                continue




            training_images.append(

                cv2.resize(enrolled_face, (200, 200))

            )



            labels.append(int(employee.id))

            employee_names[int(employee.id)] = employee



        if not training_images:

            return {

                "status": "not_enrolled",

                "message": "No employee face photos are enrolled.",

            }



        recognizer.train(

            training_images,

            np.array(labels, dtype=np.int32),

        )



        predicted_id, distance = recognizer.predict(query_face)
        print(
          f"FACE DEBUG | predicted_id={predicted_id} "
          f"| distance={distance:.2f} "
          f"| threshold=75"
        )

        print("ENROLLED EMPLOYEES:")

        for employee_id, employee in employee_names.items():
           print(
             f"DB ID={employee_id} | "
             f"Employee ID={employee.employee_id} | "
             f"Name={employee.name}"
            )



        # Temporary diagnostics: compare the saved and live face images.

        saved_face = None



        if predicted_id in labels:

            saved_face = training_images[labels.index(predicted_id)]



        if saved_face is not None:

            print(

                "IMAGE DEBUG | "

                f"saved_mean={np.mean(saved_face):.2f} | "

                f"camera_mean={np.mean(query_face):.2f} | "

                f"saved_std={np.std(saved_face):.2f} | "

                f"camera_std={np.std(query_face):.2f}"

            )



        print(

            f"FACE DEBUG | predicted_id={predicted_id} "

            f"| distance={distance:.2f} "

            f"| threshold=75"

        )



        # Keep the existing recognition threshold unchanged.

        if predicted_id not in employee_names or distance > 75:

            return {

                "status": "unrecognized",

                "message": "Face not recognized.",

            }



        employee = employee_names[predicted_id]



        open_record = (

            db.query(Attendance)

            .filter(

                Attendance.employee_id == employee.id,

                Attendance.check_out.is_(None),

            )

            .order_by(Attendance.check_in.desc())

            .first()

        )



        # ---------------- CHECK-IN ----------------



        if mode == "check-in":

            if open_record:

                return {

                    "status": "already_checked_in",

                    "employee_name": employee.name,

                    "message": (

                        f"{employee.name}, you have already checked in."

                    ),

                }



            timestamp = datetime.now()



            photo_name = (

                f"{employee.id}_checkin_"

                f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"

            )



            color_frame = cv2.imdecode(
              np.frombuffer(raw, dtype=np.uint8),
              cv2.IMREAD_COLOR,
            )

            if color_frame is None:
               raise HTTPException(
                 400,
                 "Could not decode the attendance photo.",
               )

            success, encoded = cv2.imencode(".jpg", color_frame)

            if not success:
               raise HTTPException(
                  500,
                  "Could not encode attendance photo.",
                )

            object_key = f"attendance/{photo_name}"

            try:
              upload_image(object_key, encoded.tobytes())
            except Exception:
               raise HTTPException(
                 500,
                 "Could not upload attendance photo to storage.",
                )



            db.add(

                Attendance(

                    employee_id=employee.id,

                    check_in=timestamp,

                    check_in_photo=object_key,

                    check_in_liveness=False,

                )

            )



            db.commit()



            return {

                "status": "checked_in",

                "employee_name": employee.name,

                "message": (

                    f"{employee.name}, your check-in is registered."

                ),

            }




        # ---------------- CHECK-OUT ----------------

        if not open_record:
            return {
                "status": "not_checked_in",
                "employee_name": employee.name,
                "message": (
                    f"{employee.name}, you have not checked in."
                ),
            }

        timestamp = datetime.now()

        photo_name = (
            f"{employee.id}_checkout_"
            f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        )

        color_frame = cv2.imdecode(
            np.frombuffer(raw, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )

        if color_frame is None:
            raise HTTPException(
                400,
                "Could not decode attendance photo.",
            )

        success, encoded = cv2.imencode(".jpg", color_frame)

        if not success:
            raise HTTPException(
                500,
                "Could not encode attendance photo.",
            )

        object_key = f"attendance/{photo_name}"

        try:
            upload_image(object_key, encoded.tobytes())
        except Exception as exc:
            print(
                f"CHECK-OUT STORAGE ERROR | "
                f"{type(exc).__name__}: {exc}"
            )
            raise HTTPException(
                500,
                "Could not upload check-out photo to storage.",
            )

        open_record.check_out = timestamp
        open_record.check_out_photo = object_key
        open_record.check_out_liveness = False

        db.commit()

        return {
            "status": "checked_out",
            "employee_name": employee.name,
            "message": (
                f"{employee.name}, your check-out is registered."
            ),
        }





# ---------------- EMPLOYEE PROFILE ----------------



@app.get("/api/employee/profile")

def employee_profile(user=Depends(current_user)):

    if user["role"] != "employee" or not user["employee_pk"]:

        raise HTTPException(403, "Employee account required.")



    with SessionLocal() as db:

        employee = db.get(Employee, user["employee_pk"])



        if not employee:

            raise HTTPException(404, "Employee profile not found.")



        return {

            "employee_id": employee.employee_id,

            "name": employee.name,

            "department": employee.department,

        }





# ---------------- EMPLOYEE ATTENDANCE HISTORY ----------------



@app.get("/api/employee/attendance")

def employee_attendance(user=Depends(current_user)):
    if user["role"] != "employee" or not user["employee_pk"]:
        raise HTTPException(403, "Employee account required.")

    with SessionLocal() as db:
        employee = db.get(Employee, user["employee_pk"])

        if not employee:
            raise HTTPException(404, "Employee profile not found.")

        records = (
            db.query(Attendance)
            .filter(Attendance.employee_id == employee.id)
            .order_by(Attendance.check_in.desc())
            .all()
        )

        attendance = []

        for record in records:
            check_in_photo = None
            check_out_photo = None

            if record.check_in_photo:
                check_in_photo = (
                    "/api/attendance-photo/"
                    + Path(record.check_in_photo).name
                )

            if record.check_out_photo:
                check_out_photo = (
                    "/api/attendance-photo/"
                    + Path(record.check_out_photo).name
                )

            attendance.append({
                "id": record.id,
                "date": (
                    record.check_in.strftime("%Y-%m-%d")
                    if record.check_in else None
                ),
                "check_in": (
                    record.check_in.strftime("%Y-%m-%d %H:%M:%S")
                    if record.check_in else None
                ),
                "check_out": (
                    record.check_out.strftime("%Y-%m-%d %H:%M:%S")
                    if record.check_out else None
                ),
                "check_in_photo": check_in_photo,
                "check_out_photo": check_out_photo,
                "status": (
                    "Present" if record.check_out else "Checked In"
                ),
            })

        return {
            "employee_id": employee.employee_id,
            "employee_name": employee.name,
            "total_records": len(attendance),
            "attendance": attendance,
        }

@app.get("/api/admin/attendance")
def admin_attendance(user=Depends(require_admin)):
    with SessionLocal() as db:
        records = (
            db.query(Attendance, Employee)
            .join(Employee, Attendance.employee_id == Employee.id)
            .order_by(Attendance.check_in.desc())
            .all()
        )

        attendance_records = []

        for record, employee in records:
            check_in_photo = (
                "/api/attendance-photo/" + Path(record.check_in_photo).name
                if record.check_in_photo else None
            )
            check_out_photo = (
                "/api/attendance-photo/" + Path(record.check_out_photo).name
                if record.check_out_photo else None
            )

            attendance_records.append({
                "id": record.id,
                "employee_id": employee.employee_id,
                "employee_name": employee.name,
                "department": employee.department,
                "date": (
                    record.check_in.strftime("%Y-%m-%d")
                    if record.check_in else None
                ),
                "check_in": (
                    record.check_in.strftime("%Y-%m-%d %H:%M:%S")
                    if record.check_in else None
                ),
                "check_out": (
                    record.check_out.strftime("%Y-%m-%d %H:%M:%S")
                    if record.check_out else None
                ),
                "check_in_photo": check_in_photo,
                "check_out_photo": check_out_photo,
                "status": "Present" if record.check_out else "Checked In",
            })

        return {
            "total_records": len(attendance_records),
            "attendance": attendance_records,
        }



@app.get("/api/attendance-photo/{filename}")
def get_attendance_photo(
    filename: str,
    user=Depends(current_user),
):
    if (
        not filename
        or Path(filename).name != filename
        or not filename.lower().endswith(".jpg")
    ):
        raise HTTPException(400, "Invalid photo filename.")

    object_key = f"attendance/{filename}"

    with SessionLocal() as db:
        query = db.query(Attendance).filter(
            (Attendance.check_in_photo == object_key)
            | (Attendance.check_out_photo == object_key)
        )

        if user["role"] != "admin":
            if (
                user["role"] != "employee"
                or not user["employee_pk"]
            ):
                raise HTTPException(403, "Access denied.")

            employee = db.get(Employee, user["employee_pk"])

            if not employee:
                raise HTTPException(404, "Employee not found.")

            query = query.filter(
                Attendance.employee_id == employee.id
            )

        record = query.first()

        if not record:
            raise HTTPException(
                404,
                "Photo is not linked to an accessible attendance record.",
            )

    try:
        image_bytes = download_image(object_key)
    except Exception:
        raise HTTPException(
            404,
            "Attendance photo could not be retrieved from storage.",
        )

    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )



