
import os
from datetime import datetime

from sqlalchemy import (
    create_engine,
    String,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, sessionmaker


# --------------------------------------------------
# DATABASE CONFIGURATION
# --------------------------------------------------

url = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")

url = url.replace("postgres://", "postgresql+psycopg://")

if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    url,
    connect_args={"check_same_thread": False}
    if url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


# --------------------------------------------------
# DATABASE BASE
# --------------------------------------------------

class Base(DeclarativeBase):
    pass


# --------------------------------------------------
# EMPLOYEE TABLE
# --------------------------------------------------

class Employee(Base):
    __tablename__ = "employees"

    id = mapped_column(Integer, primary_key=True)

    employee_id = mapped_column(
        String(50),
        unique=True,
        index=True,
    )

    name = mapped_column(String(120))

    department = mapped_column(String(100))

    face_data = mapped_column(
        String,
        nullable=True,
    )


# --------------------------------------------------
# ATTENDANCE TABLE
# --------------------------------------------------

class Attendance(Base):
    __tablename__ = "attendance"

    id = mapped_column(Integer, primary_key=True)

    employee_id = mapped_column(
        ForeignKey("employees.id"),
        nullable=False,
    )

    # Backend-generated attendance timestamps
    check_in = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )

    check_out = mapped_column(
        DateTime,
        nullable=True,
    )

    # Paths to the actual camera photographs.
    # The image files will be saved separately.
    check_in_photo = mapped_column(
        String,
        nullable=True,
    )

    check_out_photo = mapped_column(
        String,
        nullable=True,
    )

    # Whether the liveness check passed for each event.
    check_in_liveness = mapped_column(
        Boolean,
        nullable=True,
    )

    check_out_liveness = mapped_column(
        Boolean,
        nullable=True,
    )


# --------------------------------------------------
# USER TABLE
# --------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = mapped_column(Integer, primary_key=True)

    username = mapped_column(
        String(80),
        unique=True,
        index=True,
    )

    password_hash = mapped_column(String(255))

    role = mapped_column(
        String(20),
        default="employee",
    )

    employee_pk = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )


# --------------------------------------------------
# SAFE DATABASE INITIALIZATION / MIGRATION
# --------------------------------------------------

def initialize_database():
    # Create missing tables without deleting existing records.
    Base.metadata.create_all(bind=engine)

    # create_all() does not add columns to existing tables.
    # Add only the new attendance columns that are missing.
    inspector = inspect(engine)

    if "attendance" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("attendance")
    }

    new_columns = {
        "check_in_photo": "VARCHAR",
        "check_out_photo": "VARCHAR",
        "check_in_liveness": "BOOLEAN",
        "check_out_liveness": "BOOLEAN",
    }

    with engine.begin() as connection:
        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE attendance "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


initialize_database()
