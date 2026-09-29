import cv2
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "backend"))

from database import get_connection

FACE_DATA_DIR = BASE_DIR / "face_data"
MODEL_DIR = BASE_DIR / "models"

MODEL_DIR.mkdir(exist_ok=True)

CASCADE_PATH = BASE_DIR / "haarcascade_frontalface_default.xml"
MODEL_PATH = MODEL_DIR / "face_model.yml"


def train_face_model():

    print("\n================================")
    print("       TRAINING FACE MODEL")
    print("================================")

    face_detector = cv2.CascadeClassifier(str(CASCADE_PATH))

    if face_detector.empty():
        print("Haar Cascade file could not be loaded.")
        return

    faces = []
    labels = []
    label_names = {}

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, employee_id, name FROM employees WHERE is_active = 1"
    )

    employees = cursor.fetchall()
    connection.close()

    if not employees:
        print("No employees found in database.")
        return

    label_number = 0

    for employee in employees:

        database_id = employee["id"]
        employee_id = employee["employee_id"]
        name = employee["name"]

        employee_folder = FACE_DATA_DIR / employee_id

        if not employee_folder.exists():
            continue

        label_names[label_number] = {
            "employee_id": employee_id,
            "name": name
        }

        image_files = list(employee_folder.glob("*.jpg"))

        for image_file in image_files:

            image = cv2.imread(str(image_file), cv2.IMREAD_GRAYSCALE)

            if image is None:
                continue

            faces.append(image)
            labels.append(label_number)

        label_number += 1

    if not faces:
        print("No face images found.")
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    recognizer.train(
        faces,
        __import__("numpy").array(labels)
    )

    recognizer.write(str(MODEL_PATH))

    print("\nFace model trained successfully.")
    print(f"Employees trained : {len(label_names)}")
    print(f"Images used       : {len(faces)}")
    print(f"Model saved at    : {MODEL_PATH}")

    label_file = MODEL_DIR / "labels.txt"

    with open(label_file, "w", encoding="utf-8") as file:

        for label, data in label_names.items():

            file.write(
                f"{label}|{data['employee_id']}|{data['name']}\n"
            )

    print(f"Labels saved at   : {label_file}")

    print("================================")


if __name__ == "__main__":
    train_face_model()