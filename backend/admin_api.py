from pathlib import Path
import sqlite3
from datetime import datetime, date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = (
    BASE_DIR / "database" / "attendance.db"
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="BEL Workforce Admin API",
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
# DATABASE
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        str(DATABASE_PATH)
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "BEL Workforce Admin API is running",
        "status": "OK"
    }


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

@app.get("/api/admin/summary")
def dashboard_summary():

    today = date.today().isoformat()

    connection = get_connection()

    try:

        total_employees = connection.execute(
            """
            SELECT COUNT(*)
            FROM employees
            WHERE is_active = 1
            """
        ).fetchone()[0]


        present_today = connection.execute(
            """
            SELECT COUNT(*)
            FROM attendance
            WHERE date = ?
            AND check_in IS NOT NULL
            """,
            (today,)
        ).fetchone()[0]


        checked_out_today = connection.execute(
            """
            SELECT COUNT(*)
            FROM attendance
            WHERE date = ?
            AND check_out IS NOT NULL
            """,
            (today,)
        ).fetchone()[0]


        on_leave_today = connection.execute(
            """
            SELECT COUNT(DISTINCT employee_id)
            FROM leaves
            WHERE status = 'Approved'
            AND start_date <= ?
            AND end_date >= ?
            """,
            (today, today)
        ).fetchone()[0]


        absent_today = max(
            total_employees
            - present_today
            - on_leave_today,
            0
        )


        return {

            "date": today,

            "total_employees":
                total_employees,

            "present_today":
                present_today,

            "checked_out_today":
                checked_out_today,

            "on_leave_today":
                on_leave_today,

            "absent_today":
                absent_today

        }

    finally:

        connection.close()


# ============================================================
# ALL EMPLOYEES
# ============================================================

@app.get("/api/admin/employees")
def get_employees():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                id,
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
            ORDER BY employee_id
            """
        ).fetchall()


        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


# ============================================================
# TODAY'S ATTENDANCE
# ============================================================

@app.get("/api/admin/attendance/today")
def get_today_attendance():

    today = date.today().isoformat()

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                e.employee_id,
                e.name,
                e.department,
                e.designation,

                a.date,
                a.check_in,
                a.check_out,
                a.working_hours,
                a.status

            FROM employees e

            LEFT JOIN attendance a
                ON e.employee_id = a.employee_id
                AND a.date = ?

            WHERE e.is_active = 1

            ORDER BY e.employee_id
            """,
            (today,)
        ).fetchall()


        result = []

        for row in rows:

            item = dict(row)

            if item["check_in"]:

                if item["check_out"]:

                    item["attendance_state"] = (
                        "Checked Out"
                    )

                else:

                    item["attendance_state"] = (
                        "Checked In"
                    )

            else:

                item["attendance_state"] = (
                    "Absent"
                )


            result.append(item)


        return result

    finally:

        connection.close()


# ============================================================
# ATTENDANCE BY DATE
# ============================================================

@app.get("/api/admin/attendance/date/{attendance_date}")
def get_attendance_by_date(
    attendance_date: str
):

    try:

        datetime.strptime(
            attendance_date,
            "%Y-%m-%d"
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Date must be YYYY-MM-DD."
        )


    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                e.employee_id,
                e.name,
                e.department,
                e.designation,

                a.date,
                a.check_in,
                a.check_out,
                a.working_hours,
                a.status

            FROM employees e

            LEFT JOIN attendance a
                ON e.employee_id = a.employee_id
                AND a.date = ?

            WHERE e.is_active = 1

            ORDER BY e.employee_id
            """,
            (attendance_date,)
        ).fetchall()


        result = []

        for row in rows:

            item = dict(row)

            if item["check_in"]:

                if item["check_out"]:

                    item["attendance_state"] = (
                        "Checked Out"
                    )

                else:

                    item["attendance_state"] = (
                        "Checked In"
                    )

            else:

                item["attendance_state"] = (
                    "Absent"
                )


            result.append(item)


        return result

    finally:

        connection.close()


# ============================================================
# EMPLOYEE ATTENDANCE HISTORY
# ============================================================

@app.get(
    "/api/admin/employee/{employee_id}/attendance"
)
def employee_attendance(
    employee_id: str
):

    employee_id = employee_id.strip().upper()

    connection = get_connection()

    try:

        employee = connection.execute(
            """
            SELECT
                employee_id,
                name,
                department,
                designation
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


        rows = connection.execute(
            """
            SELECT
                date,
                check_in,
                check_out,
                working_hours,
                status,
                check_in_photo,
                check_out_photo

            FROM attendance

            WHERE employee_id = ?

            ORDER BY date DESC

            LIMIT 100
            """,
            (employee_id,)
        ).fetchall()


        return {

            "employee":
                dict(employee),

            "attendance": [
                dict(row)
                for row in rows
            ]

        }

    finally:

        connection.close()


# ============================================================
# LEAVE DATA
# ============================================================

@app.get("/api/admin/leaves")
def get_leaves():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                l.id,
                l.employee_id,
                e.name,
                e.department,
                l.leave_type,
                l.start_date,
                l.end_date,
                l.reason,
                l.status,
                l.created_at

            FROM leaves l

            LEFT JOIN employees e
                ON l.employee_id = e.employee_id

            ORDER BY l.created_at DESC
            """
        ).fetchall()


        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


# ============================================================
# PAYROLL DATA
# ============================================================

@app.get("/api/admin/payroll")
def get_payroll():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                p.id,
                p.employee_id,
                e.name,
                e.department,

                p.month,
                p.year,

                p.present_days,
                p.absent_days,
                p.leave_days,

                p.overtime_hours,

                p.basic_salary,
                p.deductions,
                p.bonus,
                p.net_salary,

                p.generated_at

            FROM payroll p

            LEFT JOIN employees e
                ON p.employee_id = e.employee_id

            ORDER BY
                p.year DESC,
                p.month DESC,
                p.employee_id
            """
        ).fetchall()


        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


# ============================================================
# DEPARTMENT SUMMARY
# ============================================================

@app.get("/api/admin/departments")
def department_summary():

    today = date.today().isoformat()

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                e.department,

                COUNT(e.employee_id)
                    AS total_employees,

                SUM(
                    CASE
                        WHEN a.check_in IS NOT NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS present_count

            FROM employees e

            LEFT JOIN attendance a
                ON e.employee_id = a.employee_id
                AND a.date = ?

            WHERE e.is_active = 1

            GROUP BY e.department

            ORDER BY e.department
            """,
            (today,)
        ).fetchall()


        result = []

        for row in rows:

            item = dict(row)

            total = (
                item["total_employees"] or 0
            )

            present = (
                item["present_count"] or 0
            )


            item["absent_count"] = (
                total - present
            )


            result.append(item)


        return result

    finally:

        connection.close()