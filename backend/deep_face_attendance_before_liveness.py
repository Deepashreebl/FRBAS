import cv2
import numpy as np
from pathlib import Path
import sqlite3
from datetime import datetime
from insightface.app import FaceAnalysis

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / "database" / "attendance.db"
EMBEDDINGS_DIR = BASE_DIR / "face_embeddings"
PHOTO_DIR = BASE_DIR / "attendance_photos" / "check_in"

PHOTO_DIR.mkdir(parents=True, exist_ok=True)

SIMILARITY_THRESHOLD = 0.55
REQUIRED_CONFIRMATIONS = 5


def load_employees():
    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT employee_id, name
        FROM employees
        WHERE is_active = 1
        """
    )

    employees = cursor.fetchall()
    connection.close()

    return employees


def mark_check_in(employee_id, name, frame):
    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, check_in
        FROM attendance
        WHERE employee_id = ? AND date = ?
        """,
        (employee_id, today)
    )

    existing = cursor.fetchone()

    if existing:
        connection.close()

        print("\n" + "=" * 55)
        print("ALREADY CHECKED IN")
        print("=" * 55)
        print(f"Employee : {name}")
        print(f"ID       : {employee_id}")
        print(f"Check-in : {existing[1]}")
        print("=" * 55)

        return False

    photo_name = (
        f"{employee_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    )

    photo_path = PHOTO_DIR / photo_name

    cv2.imwrite(str(photo_path), frame)

    cursor.execute(
        """
        INSERT INTO attendance
        (
            employee_id,
            date,
            check_in,
            status,
            check_in_photo
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            employee_id,
            today,
            current_time,
            "Present",
            str(photo_path)
        )
    )

    connection.commit()
    connection.close()

    print("\n" + "=" * 55)
    print("ATTENDANCE MARKED SUCCESSFULLY")
    print("=" * 55)
    print(f"Employee : {name}")
    print(f"ID       : {employee_id}")
    print(f"Date     : {today}")
    print(f"Check-in : {current_time}")
    print(f"Photo    : {photo_path}")
    print("=" * 55)

    return True


print("=" * 60)
print("       DEEP FACE ATTENDANCE - INSIGHTFACE")
print("=" * 60)

employees = load_employees()

if not employees:
    print("No active employees found in the database.")
    exit()

known_faces = {}

for employee_id, name in employees:

    embedding_file = EMBEDDINGS_DIR / f"{employee_id}.npy"

    if not embedding_file.exists():
        print(
            f"Warning: No deep embedding found for "
            f"{employee_id} ({name})"
        )
        continue

    embedding = np.load(str(embedding_file))

    embedding = embedding.astype(np.float32)

    norm = np.linalg.norm(embedding)

    if norm > 0:
        embedding = embedding / norm

    known_faces[employee_id] = {
        "name": name,
        "embedding": embedding
    }

if not known_faces:
    print("\nNo deep face embeddings found.")
    print("Run deep_face_registration.py first.")
    exit()

print(f"\nLoaded {len(known_faces)} employee face embeddings.")

print("\nLoading InsightFace model...")

app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

app.prepare(
    ctx_id=0,
    det_size=(640, 640)
)

print("InsightFace model loaded.")

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("ERROR: Could not open webcam.")
    exit()

confirmation_count = 0
last_employee_id = None

print("\n" + "=" * 60)
print("CAMERA STARTED")
print("=" * 60)
print("Look directly at the camera.")
print("Only ONE person should be visible.")
print("Press Q to exit.")
print("=" * 60)

while True:

    ret, frame = camera.read()

    if not ret:
        print("Could not read camera frame.")
        break

    faces = app.get(frame)

    display_frame = frame.copy()

    if len(faces) == 0:

        confirmation_count = 0
        last_employee_id = None

        cv2.putText(
            display_frame,
            "NO FACE DETECTED",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

    elif len(faces) > 1:

        confirmation_count = 0
        last_employee_id = None

        cv2.putText(
            display_frame,
            "MULTIPLE FACES - REJECTED",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

    else:

        face = faces[0]

        bbox = face.bbox.astype(int)

        x1, y1, x2, y2 = bbox

        embedding = face.embedding

        embedding = np.asarray(
            embedding,
            dtype=np.float32
        )

        norm = np.linalg.norm(embedding)

        if norm > 0:
            embedding = embedding / norm

        best_employee = None
        best_similarity = -1.0

        for employee_id, data in known_faces.items():

            known_embedding = data["embedding"]

            similarity = float(
                np.dot(
                    embedding,
                    known_embedding
                )
            )

            if similarity > best_similarity:

                best_similarity = similarity
                best_employee = employee_id

        if (
            best_employee is not None
            and best_similarity >= SIMILARITY_THRESHOLD
        ):

            employee_name = known_faces[
                best_employee
            ]["name"]

            if last_employee_id == best_employee:
                confirmation_count += 1
            else:
                confirmation_count = 1
                last_employee_id = best_employee

            cv2.rectangle(
                display_frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            cv2.putText(
                display_frame,
                f"{employee_name}",
                (x1, max(y1 - 35, 25)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                display_frame,
                f"Similarity: {best_similarity:.3f}",
                (x1, max(y1 - 10, 25)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

            cv2.putText(
                display_frame,
                f"Confirming: {confirmation_count}/{REQUIRED_CONFIRMATIONS}",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            if confirmation_count >= REQUIRED_CONFIRMATIONS:

                mark_check_in(
                    best_employee,
                    employee_name,
                    frame
                )

                cv2.putText(
                    display_frame,
                    "ATTENDANCE MARKED",
                    (30, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

                cv2.imshow(
                    "Deep Face Attendance",
                    display_frame
                )

                cv2.waitKey(2500)

                break

        else:

            confirmation_count = 0
            last_employee_id = None

            cv2.rectangle(
                display_frame,
                (x1, y1),
                (x2, y2),
                (0, 0, 255),
                2
            )

            cv2.putText(
                display_frame,
                "FACE NOT RECOGNISED",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

            cv2.putText(
                display_frame,
                f"Similarity: {best_similarity:.3f}",
                (30, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2
            )

    cv2.imshow(
        "Deep Face Attendance",
        display_frame
    )

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()

print("\nAttendance camera closed.")