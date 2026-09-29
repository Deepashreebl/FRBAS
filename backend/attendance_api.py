from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, date
from pathlib import Path
import sqlite3

# ============================================================
# PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / "database" / "attendance.db"


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="BEL Workforce Attendance API",
    description="Attendance and employee dashboard API",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

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


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "success": True,
        "message": "BEL Workforce Attendance API is running."
    }


# ============================================================
# GET EMPLOYEE INFORMATION
# ============================================================

@app.get("/api/employee/{employee_id}")
def get_employee(employee_id: str):

    connection = get_connection()

    try:

        employee = connection.execute(
            """
            SELECT
                employee_id,
                name,
                email,
                phone,
                department,
                designation,
                salary,
                created_at,
                is_active
            FROM employees
            WHERE employee_id = ?
            """,
            (employee_id,)
        ).fetchone()

        if employee is None:

            raise HTTPException(
                status_code=404,
                detail="Employee not found."
            )

        return {
            "success": True,
            "employee": dict(employee)
        }

    finally:

        connection.close()


# ============================================================
# TODAY'S ATTENDANCE
# ============================================================

@app.get("/api/attendance/{employee_id}/today")
def get_today_attendance(employee_id: str):

    today = date.today().isoformat()

    connection = get_connection()

    try:

        attendance = connection.execute(
            """
            SELECT
                employee_id,
                date,
                check_in,
                check_out,
                working_hours,
                status,
                check_in_photo,
                check_out_photo
            FROM attendance
            WHERE employee_id = ?
            AND date = ?
            """,
            (
                employee_id,
                today
            )
        ).fetchone()

        if attendance is None:

            return {
                "success": True,
                "checked_in": False,
                "checked_out": False,
                "attendance": None
            }

        data = dict(attendance)

        return {
            "success": True,
            "checked_in": bool(data.get("check_in")),
            "checked_out": bool(data.get("check_out")),
            "attendance": data
        }

    finally:

        connection.close()


# ============================================================
# RECENT ATTENDANCE
# ============================================================

@app.get("/api/attendance/{employee_id}/recent")
def get_recent_attendance(
    employee_id: str,
    limit: int = 10
):

    if limit < 1:
        limit = 10

    if limit > 50:
        limit = 50

    connection = get_connection()

    try:

        records = connection.execute(
            """
            SELECT
                date,
                check_in,
                check_out,
                working_hours,
                status
            FROM attendance
            WHERE employee_id = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (
                employee_id,
                limit
            )
        ).fetchall()

        return {
            "success": True,
            "employee_id": employee_id,
            "records": [
                dict(record)
                for record in records
            ]
        }

    finally:

        connection.close()


# ============================================================
# MONTHLY ATTENDANCE SUMMARY
# ============================================================

@app.get("/api/attendance/{employee_id}/summary")
def get_attendance_summary(employee_id: str):

    current_month = date.today().strftime("%Y-%m")

    connection = get_connection()

    try:

        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS total_records,
                SUM(
                    CASE
                        WHEN status = 'Present'
                        THEN 1
                        ELSE 0
                    END
                ) AS present_days,
                SUM(
                    CASE
                        WHEN status = 'Absent'
                        THEN 1
                        ELSE 0
                    END
                ) AS absent_days,
                COALESCE(
                    SUM(working_hours),
                    0
                ) AS total_working_hours
            FROM attendance
            WHERE employee_id = ?
            AND substr(date, 1, 7) = ?
            """,
            (
                employee_id,
                current_month
            )
        ).fetchone()

        data = dict(summary)

        return {
            "success": True,
            "month": current_month,
            "total_records": data["total_records"] or 0,
            "present_days": data["present_days"] or 0,
            "absent_days": data["absent_days"] or 0,
            "total_working_hours": round(
                float(data["total_working_hours"] or 0),
                2
            )
        }

    finally:

        connection.close()


# ============================================================
# LEAVE SUMMARY
# ============================================================

@app.get("/api/leave/{employee_id}")
def get_leave_summary(employee_id: str):

    connection = get_connection()

    try:

        records = connection.execute(
            """
            SELECT
                id,
                leave_type,
                start_date,
                end_date,
                reason,
                status,
                created_at
            FROM leaves
            WHERE employee_id = ?
            ORDER BY created_at DESC
            """,
            (employee_id,)
        ).fetchall()

        return {
            "success": True,
            "employee_id": employee_id,
            "leaves": [
                dict(record)
                for record in records
            ]
        }

    finally:

        connection.close()


# ============================================================
# PAYROLL SUMMARY
# ============================================================

@app.get("/api/payroll/{employee_id}")
def get_payroll(employee_id: str):

    connection = get_connection()

    try:

        records = connection.execute(
            """
            SELECT
                month,
                year,
                present_days,
                absent_days,
                leave_days,
                overtime_hours,
                basic_salary,
                deductions,
                bonus,
                net_salary,
                generated_at
            FROM payroll
            WHERE employee_id = ?
            ORDER BY year DESC, month DESC
            """,
            (employee_id,)
        ).fetchall()

        return {
            "success": True,
            "employee_id": employee_id,
            "payroll": [
                dict(record)
                for record in records
            ]
        }

    finally:

        connection.close()


# ============================================================
# RUN MESSAGE
# ============================================================

if __name__ == "__main__":

    print(
        "BEL Workforce Attendance API"
    )

    print(
        f"Database: {DATABASE_PATH}"
    )