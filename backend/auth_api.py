from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pathlib import Path
import sqlite3
import hashlib
import secrets
import re


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "database" / "attendance.db"


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="BEL Workforce Authentication API",
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# =========================================================
# PASSWORD SECURITY
# =========================================================

PBKDF2_ITERATIONS = 310000


def hash_password(password: str) -> str:

    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS
    )

    return (
        f"pbkdf2_sha256$"
        f"{PBKDF2_ITERATIONS}$"
        f"{salt.hex()}$"
        f"{password_hash.hex()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:

    try:

        algorithm, iterations, salt_hex, hash_hex = stored_hash.split("$")

        if algorithm != "pbkdf2_sha256":
            return False

        salt = bytes.fromhex(salt_hex)

        calculated_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations)
        )

        return secrets.compare_digest(
            calculated_hash.hex(),
            hash_hex
        )

    except Exception:
        return False


# =========================================================
# PASSWORD VALIDATION
# =========================================================

def validate_password(password: str):

    if len(password) < 8:
        return False, "Password must contain at least 8 characters."

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."

    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."

    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must contain at least one special character."

    return True, ""


# =========================================================
# SIGNUP MODEL
# =========================================================

class SignupRequest(BaseModel):

    full_name: str
    employee_id: str
    email: EmailStr
    phone: str
    department: str
    designation: str
    account_type: str = "employee"
    password: str
    confirm_password: str


# =========================================================
# LOGIN MODEL
# =========================================================

class LoginRequest(BaseModel):

    employee_id: str
    password: str

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "message": "BEL Workforce Authentication API is running."
    }


# =========================================================
# SIGNUP
# =========================================================

@app.post("/api/auth/signup")
def signup(data: SignupRequest):

    full_name = data.full_name.strip()
    employee_id = data.employee_id.strip().upper()
    email = str(data.email).strip().lower()
    phone = data.phone.strip()
    department = data.department.strip()
    designation = data.designation.strip()
    account_type = data.account_type.strip().lower()

    # -----------------------------------------------------
    # REQUIRED FIELDS
    # -----------------------------------------------------

    if not full_name:
        raise HTTPException(
            status_code=400,
            detail="Full name is required."
        )

    if not employee_id:
        raise HTTPException(
            status_code=400,
            detail="Employee ID is required."
        )

    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required."
        )

    if not department:
        raise HTTPException(
            status_code=400,
            detail="Department is required."
        )

    if not designation:
        raise HTTPException(
            status_code=400,
            detail="Designation is required."
        )

    # -----------------------------------------------------
    # PASSWORD
    # -----------------------------------------------------

    if data.password != data.confirm_password:

        raise HTTPException(
            status_code=400,
            detail="Passwords do not match."
        )

    valid, message = validate_password(data.password)

    if not valid:

        raise HTTPException(
            status_code=400,
            detail=message
        )

    # -----------------------------------------------------
    # ONLY EMPLOYEE SIGNUP
    # -----------------------------------------------------

    if account_type not in ["employee", "admin"]:

        raise HTTPException(
            status_code=400,
            detail="Invalid account type."
        )

    if account_type == "admin":

        raise HTTPException(
            status_code=403,
            detail=(
                "Admin / HR accounts cannot be created through "
                "public signup."
            )
        )

    connection = get_connection()

    try:

        cursor = connection.cursor()

        # -------------------------------------------------
        # EMAIL CHECK
        # -------------------------------------------------

        existing_email = cursor.execute(
            """
            SELECT employee_id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if existing_email:

            raise HTTPException(
                status_code=409,
                detail="An account already exists with this email address."
            )

        # -------------------------------------------------
        # EMPLOYEE CHECK
        # -------------------------------------------------

        employee = cursor.execute(
            """
            SELECT *
            FROM employees
            WHERE employee_id = ?
            """,
            (employee_id,)
        ).fetchone()

        if employee:

            existing_employee_email = employee["email"]

            if (
                existing_employee_email
                and existing_employee_email.lower() != email.lower()
            ):

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This Employee ID is already registered "
                        "with another email address."
                    )
                )

            cursor.execute(
                """
                UPDATE employees
                SET
                    name = ?,
                    email = ?,
                    phone = ?,
                    department = ?,
                    designation = ?
                WHERE employee_id = ?
                """,
                (
                    full_name,
                    email,
                    phone,
                    department,
                    designation,
                    employee_id
                )
            )

        else:

            cursor.execute(
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
                    is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    employee_id,
                    full_name,
                    email,
                    phone,
                    department,
                    designation,
                    0,
                    1
                )
            )

        # -------------------------------------------------
        # USER ACCOUNT CHECK
        # -------------------------------------------------

        existing_user = cursor.execute(
            """
            SELECT id
            FROM users
            WHERE employee_id = ?
            """,
            (employee_id,)
        ).fetchone()

        if existing_user:

            raise HTTPException(
                status_code=409,
                detail="An account already exists for this Employee ID."
            )

        # -------------------------------------------------
        # CREATE USER
        # -------------------------------------------------

        password_hash = hash_password(data.password)

        cursor.execute(
            """
            INSERT INTO users
            (
                employee_id,
                email,
                password_hash,
                role,
                is_active
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                employee_id,
                email,
                password_hash,
                "employee",
                1
            )
        )

        # -------------------------------------------------
        # AUDIT LOG
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                employee_id,
                action,
                details
            )
            VALUES (?, ?, ?)
            """,
            (
                employee_id,
                "ACCOUNT_CREATED",
                "Employee account created through BEL Workforce signup."
            )
        )

        connection.commit()

        return {
            "success": True,
            "message": "Account created successfully.",
            "employee_id": employee_id,
            "role": "employee"
        }

    except HTTPException:
        connection.rollback()
        raise

    except sqlite3.IntegrityError as error:

        connection.rollback()

        raise HTTPException(
            status_code=409,
            detail=f"Account could not be created: {str(error)}"
        )

    finally:

        connection.close()


# =========================================================
# LOGIN
# =========================================================

@app.post("/api/auth/login")
def login(data: LoginRequest):

    employee_id = data.employee_id.strip().upper()
    password = data.password

    if not employee_id:
        raise HTTPException(
            status_code=400,
            detail="Employee ID is required."
        )

    if not password:
        raise HTTPException(
            status_code=400,
            detail="Password is required."
        )

    connection = get_connection()

    try:

        cursor = connection.cursor()

        # -------------------------------------------------
        # FIND USER BY EMPLOYEE ID
        # -------------------------------------------------

        user = cursor.execute(
            """
            SELECT
                u.employee_id,
                u.email,
                u.password_hash,
                u.role,
                u.is_active,
                e.name,
                e.department,
                e.designation
            FROM users u
            JOIN employees e
                ON u.employee_id = e.employee_id
            WHERE UPPER(u.employee_id) = UPPER(?)
            """,
            (employee_id,)
        ).fetchone()

        # -------------------------------------------------
        # ACCOUNT NOT FOUND
        # -------------------------------------------------

        if not user:

            raise HTTPException(
                status_code=401,
                detail="Invalid Employee ID or password."
            )

        # -------------------------------------------------
        # ACCOUNT INACTIVE
        # -------------------------------------------------

        if user["is_active"] != 1:

            raise HTTPException(
                status_code=403,
                detail="This account is inactive."
            )

        # -------------------------------------------------
        # PASSWORD CHECK
        # -------------------------------------------------

        if not verify_password(
            password,
            user["password_hash"]
        ):

            raise HTTPException(
                status_code=401,
                detail="Invalid Employee ID or password."
            )

        # -------------------------------------------------
        # AUDIT LOG
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                employee_id,
                action,
                details
            )
            VALUES (?, ?, ?)
            """,
            (
                user["employee_id"],
                "LOGIN",
                "Successful login to BEL Workforce."
            )
        )

        connection.commit()

        return {
            "success": True,
            "message": "Login successful.",
            "employee_id": user["employee_id"],
            "name": user["name"],
            "email": user["email"],
            "department": user["department"],
            "designation": user["designation"],
            "role": user["role"]
        }

    finally:

        connection.close()

# =========================================================
# RUN DIRECTLY
# =========================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "backend.auth_api:app",
        host="127.0.0.1",
        port=8001,
        reload=True
    )