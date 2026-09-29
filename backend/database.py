import sqlite3
from pathlib import Path


# Get the main project folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Database folder
DATABASE_DIR = BASE_DIR / "database"
DATABASE_DIR.mkdir(exist_ok=True)

# Database file
DATABASE_PATH = DATABASE_DIR / "attendance.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)

    # Allows us to access columns by their names
    connection.row_factory = sqlite3.Row

    # Enable foreign key relationships
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_tables():

    connection = get_connection()
    cursor = connection.cursor()

    # ==========================================
    # 1. EMPLOYEES TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            department TEXT,
            designation TEXT,
            salary REAL DEFAULT 0,
            face_encoding TEXT,
            photo_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)

    # ==========================================
    # 2. USERS TABLE
    # ==========================================
    # Used for website login and authentication.
    # Passwords will be stored as secure hashes,
    # NOT as plain text.

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (employee_id)
            REFERENCES employees(employee_id)
            ON DELETE CASCADE
        )
    """)

    # ==========================================
    # 3. ATTENDANCE TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            working_hours REAL DEFAULT 0,
            status TEXT DEFAULT 'Present',
            check_in_photo TEXT,
            check_out_photo TEXT,

            FOREIGN KEY (employee_id)
            REFERENCES employees(employee_id)
            ON DELETE CASCADE,

            UNIQUE(employee_id, date)
        )
    """)

    # ==========================================
    # 4. LEAVE TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            leave_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (employee_id)
            REFERENCES employees(employee_id)
            ON DELETE CASCADE
        )
    """)

    # ==========================================
    # 5. PAYROLL TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            present_days INTEGER DEFAULT 0,
            absent_days INTEGER DEFAULT 0,
            leave_days INTEGER DEFAULT 0,
            overtime_hours REAL DEFAULT 0,
            basic_salary REAL DEFAULT 0,
            deductions REAL DEFAULT 0,
            bonus REAL DEFAULT 0,
            net_salary REAL DEFAULT 0,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (employee_id)
            REFERENCES employees(employee_id)
            ON DELETE CASCADE,

            UNIQUE(employee_id, month, year)
        )
    """)

    # ==========================================
    # 6. AUDIT LOG TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            action TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        )
    """)

    connection.commit()
    connection.close()

    print("Database tables created successfully!")


# Run database creation
if __name__ == "__main__":
    create_tables()