import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "database" / "attendance.db"


def view_attendance_history():

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                a.id,
                e.employee_id,
                e.name,
                a.date,
                a.check_in,
                a.check_out,
                a.working_hours,
                a.status,
                a.check_in_photo,
                a.check_out_photo
            FROM attendance a
            JOIN employees e
                ON a.employee_id = e.employee_id
            ORDER BY
                a.date DESC,
                a.check_in DESC
            """
        )

        records = cursor.fetchall()

        print()
        print("=" * 100)
        print("ATTENDANCE HISTORY")
        print("=" * 100)

        if not records:

            print("No attendance records found.")
            return

        for record in records:

            print()
            print("-" * 100)

            print(
                f"Employee ID    : "
                f"{record['employee_id']}"
            )

            print(
                f"Name           : "
                f"{record['name']}"
            )

            print(
                f"Date           : "
                f"{record['date']}"
            )

            print(
                f"Check-in       : "
                f"{record['check_in'] or 'Not marked'}"
            )

            print(
                f"Check-out      : "
                f"{record['check_out'] or 'Not marked'}"
            )

            print(
                f"Working hours  : "
                f"{record['working_hours'] or 'Not calculated'}"
            )

            print(
                f"Status         : "
                f"{record['status'] or 'N/A'}"
            )

            print(
                f"Check-in photo : "
                f"{record['check_in_photo'] or 'None'}"
            )

            print(
                f"Check-out photo: "
                f"{record['check_out_photo'] or 'None'}"
            )

        print()
        print("=" * 100)
        print(
            f"Total attendance records: {len(records)}"
        )
        print("=" * 100)

    finally:

        connection.close()


if __name__ == "__main__":

    view_attendance_history()