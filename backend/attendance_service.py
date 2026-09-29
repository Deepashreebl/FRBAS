import cv2
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "backend"))

from database import get_connection


MODEL_PATH = BASE_DIR / "models" / "face_model.yml"
LABEL_PATH = BASE_DIR / "models" / "labels.txt"
CASCADE_PATH = BASE_DIR / "haarcascade_frontalface_default.xml"

PHOTO_DIR = BASE_DIR / "attendance_photos" / "check_in"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)


def load_labels():

    labels = {}

    with open(LABEL_PATH, "r", encoding="utf-8") as file:

        for line in file:

            line = line.strip()

            if not line:
                continue

            parts = line.split("|")

            label = int(parts[0])
            employee_id = parts[1]
            name = parts[2]

            labels[label] = {
                "employee_id": employee_id,
                "name": name
            }

    return labels


def mark_check_in(employee_id, name, photo_path):

    connection = get_connection()
    cursor = connection.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    cursor.execute(
        """
        SELECT id, check_in
        FROM attendance
        WHERE employee_id = ?
        AND date = ?
        """,
        (employee_id, today)
    )

    existing_record = cursor.fetchone()

    if existing_record:

        connection.close()

        print("\n================================")
        print("      ALREADY CHECKED IN")
        print("================================")
        print(f"Employee : {name}")
        print(f"ID       : {employee_id}")
        print(f"Check-in : {existing_record['check_in']}")
        print("================================")

        return False

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

    print("\n================================")
    print("       ATTENDANCE MARKED")
    print("================================")
    print(f"Employee : {name}")
    print(f"ID       : {employee_id}")
    print(f"Date     : {today}")
    print(f"Check-in : {current_time}")
    print("Status   : Present")
    print("================================")

    return True


def start_attendance():

    print("\n================================")
    print("       SMART ATTENDANCE")
    print("================================")
    print("Starting camera...")
    print("Look at the camera.")
    print("Press Q to exit.")
    print("================================")

    if not MODEL_PATH.exists():

        print("Face model not found.")
        return

    if not LABEL_PATH.exists():

        print("Labels file not found.")
        return

    face_detector = cv2.CascadeClassifier(
        str(CASCADE_PATH)
    )

    if face_detector.empty():

        print("Haar Cascade file could not be loaded.")
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    recognizer.read(
        str(MODEL_PATH)
    )

    labels = load_labels()

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print("Could not open camera.")
        return

    attendance_marked = False

    while True:

        ret, frame = camera.read()

        if not ret:

            print("Could not read camera.")
            break

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        faces = face_detector.detectMultiScale(
            gray,
            scaleFactor=1.3,
            minNeighbors=5,
            minSize=(100, 100)
        )

        if len(faces) > 1:

            cv2.putText(
                frame,
                "Multiple faces - rejected",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        elif len(faces) == 1:

            x, y, w, h = faces[0]

            face = gray[y:y + h, x:x + w]

            label, confidence = recognizer.predict(face)
            print("Detected label:", label, "Confidence:", confidence)

            if label in labels and confidence < 70:

                employee = labels[label]

                employee_id = employee["employee_id"]
                name = employee["name"]

                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"Recognized: {name}",
                    (x, y - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"ID: {employee_id}",
                    (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

                if not attendance_marked:

                    now = datetime.now()

                    photo_name = (
                        f"{employee_id}_"
                        f"{now.strftime('%Y%m%d_%H%M%S')}.jpg"
                    )

                    photo_path = PHOTO_DIR / photo_name

                    cv2.imwrite(
                        str(photo_path),
                        frame
                    )

                    success = mark_check_in(
                        employee_id,
                        name,
                        photo_path
                    )

                    if success:
                        attendance_marked = True

            else:

                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    (0, 0, 255),
                    2
                )

                cv2.putText(
                    frame,
                    "Face not recognized",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )

        cv2.imshow(
            "Smart Attendance",
            frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    start_attendance()