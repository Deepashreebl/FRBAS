import cv2
import numpy as np
from pathlib import Path
import sqlite3
from insightface.app import FaceAnalysis

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "database" / "attendance.db"
EMBEDDINGS_DIR = BASE_DIR / "face_embeddings"

EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)


def get_employee(employee_id):
    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, employee_id, name
        FROM employees
        WHERE employee_id = ? AND is_active = 1
        """,
        (employee_id,)
    )

    employee = cursor.fetchone()
    connection.close()

    return employee


print("=" * 55)
print("       DEEP FACE REGISTRATION - INSIGHTFACE")
print("=" * 55)

employee_id = input("Enter Employee ID: ").strip()

employee = get_employee(employee_id)

if employee is None:
    print("\nEmployee not found in database.")
    print("Register the employee in the database first.")
    exit()

print(f"\nEmployee found:")
print(f"Name : {employee[2]}")
print(f"ID   : {employee[1]}")

print("\nLoading InsightFace model...")
print("The first run may take some time.")

app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

app.prepare(
    ctx_id=0,
    det_size=(640, 640)
)

print("InsightFace model loaded successfully.")

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("ERROR: Could not open webcam.")
    exit()

embeddings = []
required_samples = 20

print("\n" + "=" * 55)
print("FACE CAPTURE STARTED")
print("=" * 55)
print("Look directly at the camera.")
print("Keep only ONE person in the frame.")
print("Move your head slowly left and right.")
print("Press Q to cancel.")
print(f"Required samples: {required_samples}")
print("=" * 55)

while len(embeddings) < required_samples:

    ret, frame = camera.read()

    if not ret:
        print("Could not read camera frame.")
        break

    faces = app.get(frame)

    display_frame = frame.copy()

    if len(faces) == 0:

        cv2.putText(
            display_frame,
            "NO FACE DETECTED",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2
        )

    elif len(faces) > 1:

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

        cv2.rectangle(
            display_frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

        embedding = face.embedding

        if embedding is not None:

            embedding = np.asarray(
                embedding,
                dtype=np.float32
            )

            norm = np.linalg.norm(embedding)

            if norm > 0:

                embedding = embedding / norm

                embeddings.append(embedding)

                cv2.putText(
                    display_frame,
                    f"CAPTURED: {len(embeddings)}/{required_samples}",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

    cv2.imshow(
        "Deep Face Registration",
        display_frame
    )

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        print("\nRegistration cancelled.")
        camera.release()
        cv2.destroyAllWindows()
        exit()

camera.release()
cv2.destroyAllWindows()

if len(embeddings) < required_samples:

    print("\nRegistration failed.")
    print(f"Only {len(embeddings)} samples captured.")

    exit()

embeddings = np.asarray(
    embeddings,
    dtype=np.float32
)

# Average the captured embeddings
mean_embedding = np.mean(
    embeddings,
    axis=0
)

# Normalize final embedding
mean_embedding = mean_embedding / np.linalg.norm(mean_embedding)

embedding_file = EMBEDDINGS_DIR / f"{employee_id}.npy"

np.save(
    embedding_file,
    mean_embedding
)

print("\n" + "=" * 55)
print("DEEP FACE REGISTRATION SUCCESSFUL")
print("=" * 55)
print(f"Employee : {employee[2]}")
print(f"ID       : {employee[1]}")
print(f"Samples  : {len(embeddings)}")
print(f"Embedding size : {len(mean_embedding)}")
print(f"Saved at : {embedding_file}")
print("=" * 55)