# BEL Workforce – Smart Employee Attendance & Payroll Management System

## Project Overview

This is an existing working project for a smart employee attendance and payroll management system.

The project is being developed using Python, FastAPI, SQLite, OpenCV, InsightFace, MediaPipe, HTML, CSS and JavaScript.

The project should be continued from the existing implementation. Do not redesign or replace working functionality unless specifically requested.

---

# GitHub Repository

Repository:

https://github.com/Deepashreebl/FRBAS.git

Repository visibility:

PRIVATE

The repository contains source code as well as authorized employee/attendance data required for the current development setup.

---

# Local Project

Personal PC project path:

C:\Users\HP\Desktop\SmartAttendanceSystem

---

# Technology Stack

- Python 3.12.10
- FastAPI
- Uvicorn
- SQLite
- OpenCV
- OpenCV-Contrib
- InsightFace
- ONNX Runtime
- MediaPipe
- Pyttsx3
- OpenPyXL
- Pandas
- HTML
- CSS
- JavaScript
- VS Code
- Windows PowerShell

---

# Main Architecture

The project has three separate web interfaces.

## 1. Attendance Website

Purpose:

Actual employee attendance marking.

Features:

- Employee ID entry
- Check In
- Check Out
- Camera
- Face recognition
- Liveness verification
- Attendance marking
- Attendance photo saving
- Voice announcement

URL:

http://127.0.0.1:5500/attendance/

---

## 2. Employee Dashboard

Purpose:

Employees can view their own attendance and employee information.

URL:

http://127.0.0.1:5500/employee/dashboard.html

---

## 3. Admin Dashboard

Purpose:

Admin can view and manage employee attendance and related information.

URL:

http://127.0.0.1:5500/admin/dashboard.html

---

# Database

Database type:

SQLite

Database file:

database/attendance.db

Tables:

- employees
- attendance
- leaves
- payroll
- audit_logs
- users

The same database is used by the attendance system, employee dashboard and admin dashboard.

---

# Current Employee

Employee ID:

EMP001

Employee name:

Deepashree B L

Current employee-related data:

face_embeddings/EMP001.npy

employee_photos/EMP001.jpeg

---

# Face Recognition

The project uses InsightFace for face recognition.

Employee embeddings are stored in:

face_embeddings/

Current embedding:

face_embeddings/EMP001.npy

The face recognition system uses cosine similarity.

Current similarity threshold:

0.55

Required recognition confirmations:

5

---

# Liveness Detection

The project uses MediaPipe for liveness verification.

Model:

models/face_landmarker.task

Important settings:

SIMILARITY_THRESHOLD = 0.55

REQUIRED_CONFIRMATIONS = 5

LIVENESS_TIMEOUT_SECONDS = 30

EAR_THRESHOLD = 0.21

CLOSED_FRAMES_REQUIRED = 2

AMBIGUOUS_FACE_RATIO = 0.70

MIN_FACE_AREA_RATIO = 0.015

VOICE_COOLDOWN_SECONDS = 5

The system uses blink detection as part of liveness verification.

---

# Working Face Attendance System

Main file:

backend/deep_face_attendance.py

The system has successfully performed:

- Camera opening
- Liveness verification
- Blink detection
- Face recognition
- Employee identification
- Attendance checking
- Check-in/check-out status checking
- Attendance photo saving
- Excel update
- Voice announcements

A successful test recognized:

EMP001 - Deepashree B L

with similarity:

0.683

---

# Attendance Photos

Check-in photos:

attendance_photos/check_in/

Check-out photos:

attendance_photos/check_out/

Current employee attendance photos are stored there.

---

# Excel Reports

Excel report:

excel_reports/attendance_database.xlsx

The attendance system updates the Excel report when attendance is processed.

---

# Backend Services

## Frontend Server

Port:

5500

Command:

python -m http.server 5500 --directory frontend

---

## Authentication API

Port:

8001

Purpose:

- Login
- Signup
- User authentication

---

## Employee / Attendance API

Port:

8002

Purpose:

Employee attendance and dashboard-related API operations.

---

## Camera Attendance API

Port:

8003

Run:

python -m uvicorn backend.camera_attendance_api:app --host 127.0.0.1 --port 8003 --reload

---

## Admin API

Port:

8004

Run:

python -m uvicorn backend.admin_api:app --host 127.0.0.1 --port 8004 --reload

---

# Authentication

Website name:

BEL Workforce

Subtitle:

Smart Employee Attendance & Payroll Management System

Login uses:

- Employee ID
- Password

Signup password rules:

- Minimum 8 characters
- Uppercase letter
- Lowercase letter
- Number
- Special character

Roles:

- employee
- admin

---

# Project Structure

```text
SmartAttendanceSystem/
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── face_service.py
│   ├── attendance_service.py
│   ├── payroll_service.py
│   ├── face_registration.py
│   ├── face_recognition.py
│   ├── recognize_face.py
│   ├── deep_face_registration.py
│   ├── deep_face_attendance.py
│   ├── deep_face_attendance_backup.py
│   ├── deep_face_attendance_before_liveness.py
│   ├── liveness_service.py
│   ├── employee_registration.py
│   ├── view_employees.py
│   ├── attendance_history.py
│   ├── excel_export.py
│   ├── location_service.py
│   ├── gps_api.py
│   ├── auth_api.py
│   ├── attendance_api.py
│   ├── camera_attendance_api.py
│   └── admin_api.py
│
├── frontend/
│   ├── index.html
│   ├── signup.html
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── auth,js
│   ├── admin/
│   │   └── dashboard.html
│   ├── employee/
│   │   └── dashboard.html
│   └── attendance/
│       └── index.html
│
├── database/
│   └── attendance.db
│
├── face_data/
│
├── face_embeddings/
│   └── EMP001.npy
│
├── employee_photos/
│   └── EMP001.jpeg
│
├── attendance_photos/
│   ├── check_in/
│   └── check_out/
│
├── excel_reports/
│   └── attendance_database.xlsx
│
├── models/
│   ├── face_landmarker.task
│   ├── face_model.yml
│   └── labels.txt
│
├── requirements.txt
├── .gitignore
└── PROJECT_HANDOVER.md