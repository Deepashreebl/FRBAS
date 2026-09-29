import cv2
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "models" / "face_model.yml"
LABEL_PATH = BASE_DIR / "models" / "labels.txt"
CASCADE_PATH = BASE_DIR / "haarcascade_frontalface_default.xml"


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


def recognize_face():

    print("\n================================")
    print("       FACE RECOGNITION")
    print("================================")

    if not MODEL_PATH.exists():
        print("Face model not found.")
        print(MODEL_PATH)
        return

    if not LABEL_PATH.exists():
        print("Labels file not found.")
        print(LABEL_PATH)
        return

    face_detector = cv2.CascadeClassifier(str(CASCADE_PATH))

    if face_detector.empty():
        print("Haar Cascade file could not be loaded.")
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    recognizer.read(str(MODEL_PATH))

    labels = load_labels()

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("Could not open camera.")
        return

    print("Camera started.")
    print("Look at the camera.")
    print("Press Q to exit.")

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

        for (x, y, w, h) in faces:

            face = gray[y:y + h, x:x + w]

            label, confidence = recognizer.predict(face)

            if label in labels and confidence < 45:

                employee = labels[label]

                employee_id = employee["employee_id"]
                name = employee["name"]

                text = f"{name} ({employee_id})"

                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    "Recognized",
                    (x, y - 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    text,
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

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
            "Smart Attendance - Face Recognition",
            frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    recognize_face()