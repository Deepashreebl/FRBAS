from pathlib import Path
import sqlite3
import sys

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from excel_export import export_database_to_excel


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / "database" / "attendance.db"
EMPLOYEE_PHOTOS_DIR = BASE_DIR / "employee_photos"
EMBEDDINGS_DIR = BASE_DIR / "face_embeddings"


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ============================================================
# INPUT HELPERS
# ============================================================

def get_required_input(message):
    while True:
        value = input(message).strip()

        if value:
            return value

        print("This field cannot be empty.")


def get_optional_input(message):
    return input(message).strip()


def get_salary():
    while True:
        value = input("Salary: ").strip()

        try:
            salary = float(value)

            if salary < 0:
                print("Salary cannot be negative.")
                continue

            return salary

        except ValueError:
            print("Please enter a valid salary.")


# ============================================================
# CHECK EMPLOYEE ID
# ============================================================

def employee_exists(employee_id):

    conn = get_connection()

    row = conn.execute(
        """
        SELECT id
        FROM employees
        WHERE employee_id = ?
        """,
        (employee_id,),
    ).fetchone()

    conn.close()

    return row is not None


# ============================================================
# LOAD INSIGHTFACE
# ============================================================

def load_face_model():

    print()
    print("Loading InsightFace model...")

    app = FaceAnalysis(
        name="buffalo_l",
        providers=["CPUExecutionProvider"]
    )

    app.prepare(
        ctx_id=0,
        det_size=(640, 640)
    )

    print("InsightFace model loaded.")

    return app


# ============================================================
# GENERATE FACE EMBEDDING
# ============================================================

def generate_embedding(face_app, photo_path):

    print()
    print("Reading employee photo...")

    image = cv2.imread(str(photo_path))

    if image is None:
        print("ERROR: Could not read the image.")
        return None

    print("Detecting face...")

    faces = face_app.get(image)

    # --------------------------------------------------------
    # No face
    # --------------------------------------------------------

    if len(faces) == 0:

        print()
        print("ERROR: No face detected.")
        print("Please upload a clear front-facing photo.")

        return None

    # --------------------------------------------------------
    # Multiple faces
    # --------------------------------------------------------

    if len(faces) > 1:

        print()
        print(
            f"ERROR: {len(faces)} faces detected."
        )

        print(
            "The employee photo must contain "
            "exactly ONE person."
        )

        return None

    # --------------------------------------------------------
    # One face
    # --------------------------------------------------------

    face = faces[0]

    embedding = face.embedding

    norm = np.linalg.norm(embedding)

    if norm == 0:

        print("ERROR: Invalid face embedding.")
        return None

    embedding = embedding / norm

    print()
    print("Face detected successfully.")
    print("Face embedding generated.")

    return embedding


# ============================================================
# SAVE EMPLOYEE PHOTO
# ============================================================

def save_employee_photo(employee_id, source_path):

    EMPLOYEE_PHOTOS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    extension = source_path.suffix.lower()

    if extension not in [".jpg", ".jpeg", ".png"]:

        extension = ".jpg"

    destination = (
        EMPLOYEE_PHOTOS_DIR
        / f"{employee_id}{extension}"
    )

    image = cv2.imread(str(source_path))

    if image is None:
        return None

    success = cv2.imwrite(
        str(destination),
        image
    )

    if not success:
        return None

    return destination


# ============================================================
# SAVE DATABASE RECORD
# ============================================================

def save_employee(
    employee_id,
    name,
    email,
    phone,
    department,
    designation,
    salary,
    photo_path
):

    conn = get_connection()

    try:

        conn.execute(
            """
            INSERT INTO employees
            (
                employee_id,
                name,
                email,
                phone,
                department,
                designation,
                salary,
                photo_path,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                employee_id,
                name,
                email,
                phone,
                department,
                designation,
                salary,
                str(photo_path),
                1,
            ),
        )

        conn.commit()

        return True

    except sqlite3.IntegrityError as error:

        print()
        print("Database error:")
        print(error)

        return False

    finally:

        conn.close()


# ============================================================
# SAVE FACE EMBEDDING
# ============================================================

def save_embedding(employee_id, embedding):

    EMBEDDINGS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    embedding_path = (
        EMBEDDINGS_DIR
        / f"{employee_id}.npy"
    )

    np.save(
        embedding_path,
        embedding
    )

    return embedding_path


# ============================================================
# MAIN REGISTRATION
# ============================================================

def register_employee():

    print()
    print("=" * 60)
    print("          NEW EMPLOYEE REGISTRATION")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # Employee details
    # --------------------------------------------------------

    employee_id = get_required_input(
        "Employee ID: "
    )

    if employee_exists(employee_id):

        print()
        print(
            f"ERROR: Employee ID "
            f"{employee_id} already exists."
        )

        return

    name = get_required_input(
        "Name: "
    )

    phone = get_required_input(
        "Phone number: "
    )

    email = get_optional_input(
        "Email: "
    )

    department = get_optional_input(
        "Department: "
    )

    designation = get_optional_input(
        "Designation: "
    )

    salary = get_salary()

    # --------------------------------------------------------
    # Photo
    # --------------------------------------------------------

    print()
    print("Enter the COMPLETE path of the employee photo.")
    print("Example:")
    print(
        r"C:\Users\HP\Desktop\employee_photo.jpg"
    )
    print()

    photo_input = get_required_input(
        "Photo path: "
    )

    photo_path = Path(
        photo_input.strip('"')
    )

    if not photo_path.exists():

        print()
        print("ERROR: Photo file not found.")
        print(photo_path)

        return

    if photo_path.suffix.lower() not in [
        ".jpg",
        ".jpeg",
        ".png",
    ]:

        print()
        print(
            "ERROR: Only JPG, JPEG and PNG "
            "images are supported."
        )

        return

    # --------------------------------------------------------
    # Load face model
    # --------------------------------------------------------

    face_app = load_face_model()

    # --------------------------------------------------------
    # Generate embedding
    # --------------------------------------------------------

    embedding = generate_embedding(
        face_app,
        photo_path
    )

    if embedding is None:

        print()
        print("Registration cancelled.")

        return

    # --------------------------------------------------------
    # Save photo
    # --------------------------------------------------------

    saved_photo = save_employee_photo(
        employee_id,
        photo_path
    )

    if saved_photo is None:

        print()
        print(
            "ERROR: Could not save employee photo."
        )

        return

    # --------------------------------------------------------
    # Save database record
    # --------------------------------------------------------

    success = save_employee(
        employee_id,
        name,
        email,
        phone,
        department,
        designation,
        salary,
        saved_photo
    )

    if not success:

        print()
        print(
            "Employee registration failed."
        )

        return

    # --------------------------------------------------------
    # Save embedding
    # --------------------------------------------------------

    embedding_path = save_embedding(
        employee_id,
        embedding
    )
        # --------------------------------------------------------
    # AUTOMATIC EXCEL UPDATE
    # --------------------------------------------------------

    print()
    print("Updating Excel database...")

    try:
        export_database_to_excel()
        print("Excel database updated automatically.")
    except PermissionError:
        print()
        print("WARNING: Excel file is currently open.")
        print("Close attendance_database.xlsx to allow the next update.")

    # --------------------------------------------------------
    # Success
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("       EMPLOYEE REGISTERED SUCCESSFULLY")
    print("=" * 60)
    print()
    print(f"Employee ID : {employee_id}")
    print(f"Name        : {name}")
    print(f"Phone       : {phone}")
    print(f"Email       : {email}")
    print(f"Department  : {department}")
    print(f"Designation : {designation}")
    print(f"Salary      : {salary}")
    print()
    print(f"Photo saved : {saved_photo}")
    print(f"Face data   : {embedding_path}")
    print()
    print("The employee is now ready for attendance.")
    print("=" * 60)


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":
    register_employee()

