from pathlib import Path
import sqlite3


# Project base folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Database path
DATABASE_PATH = BASE_DIR / "database" / "attendance.db"

# Face embeddings folder
EMBEDDINGS_DIR = BASE_DIR / "face_embeddings"


def view_employees():
    if not DATABASE_PATH.exists():
        print("ERROR: Database file not found.")
        print(f"Expected location: {DATABASE_PATH}")
        return

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            employee_id,
            name,
            email,
            phone,
            department,
            designation,
            salary,
            photo_path,
            created_at,
            is_active
        FROM employees
        ORDER BY id
    """)

    employees = cursor.fetchall()

    connection.close()

    if not employees:
        print("\nNo employees found in the database.")
        return

    print("\n" + "=" * 90)
    print("                 REGISTERED EMPLOYEES")
    print("=" * 90)

    print(f"Total Employees: {len(employees)}")

    for number, employee in enumerate(employees, start=1):

        employee_id = employee["employee_id"]

        # Check whether deep face embedding exists
        embedding_file = EMBEDDINGS_DIR / f"{employee_id}.npy"
        embedding_status = (
            "Available" if embedding_file.exists() else "MISSING"
        )

        print("\n" + "-" * 90)
        print(f"Employee #{number}")
        print("-" * 90)

        print(f"Employee ID       : {employee_id}")
        print(f"Name              : {employee['name']}")
        print(f"Phone             : {employee['phone'] or 'Not provided'}")
        print(f"Email             : {employee['email'] or 'Not provided'}")
        print(f"Department        : {employee['department'] or 'Not provided'}")
        print(f"Designation       : {employee['designation'] or 'Not provided'}")
        print(f"Salary            : {employee['salary'] or 'Not provided'}")
        print(f"Photo Path        : {employee['photo_path'] or 'Not provided'}")
        print(f"Face Embedding    : {embedding_status}")
        print(f"Active            : {'Yes' if employee['is_active'] else 'No'}")
        print(f"Registered On     : {employee['created_at']}")

    print("\n" + "=" * 90)


if __name__ == "__main__":
    view_employees()