import cv2
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "backend"))

from database import get_connection

FACE_DATA_DIR = BASE_DIR / "face_data"
FACE_DATA_DIR.mkdir(exist_ok=True)

CASCADE_PATH = BASE_DIR / "haarcascade_frontalface_default.xml"


def register_employee():

    print("\n================================")
    print("       EMPLOYEE REGISTRATION")
    print("================================")

    employee_id = input("Enter Employee ID: ").strip()
    name = input("Enter Employee Name: ").strip()
    email = input("Enter Email: ").strip()
    phone = input("Enter Phone Number: ").strip()
    department = input("Enter Department: ").strip()
    designation = input("Enter Designation: ").strip()
    salary_input = input("Enter Monthly Salary: ").strip()

    if not employee_id or not name:
        print("\nEmployee ID and Name are required.")
        return

    try:
        salary = float(salary_input)
    except ValueError:
        print("\nInvalid salary.")
        return

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT employee_id FROM employees WHERE employee_id = ?",
        (employee_id,)
    )

    existing_employee = cursor.fetchone()

    if existing_employee:
        connection.close()
        print("\nEmployee ID already exists.")
        return

    connection.close()

    employee_folder = FACE_DATA_DIR / employee_id
    employee_folder.mkdir(exist_ok=True)

    print("\n================================")
    print("         CAMERA SETUP")
    print("================================")
    print("Opening camera...")
    print("Look directly at the camera.")
    print("The system will capture 20 face images.")
    print("Move your head slightly in different directions.")
    print("Press Q to cancel.")
    print("================================")

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("\nCould not open camera.")
        print("Please check your webcam.")
        return

    face_detector = cv2.CascadeClassifier(str(CASCADE_PATH))

    if face_detector.empty():
        print("\nHaar Cascade file could not be loaded.")
        print("Expected file:")
        print(CASCADE_PATH)
        camera.release()
        return

    print("\nCamera started successfully.")

    count = 0

    while True:

        ret, frame = camera.read()

        if not ret:
            print("\nCould not read camera.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_detector.detectMultiScale(
            gray,
            scaleFactor=1.3,
            minNeighbors=5,
            minSize=(100, 100)
        )

        if len(faces) == 0:

            cv2.putText(
                frame,
                "No face detected",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

        elif len(faces) > 1:

            cv2.putText(
                frame,
                "Multiple faces detected",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

        else:

            x, y, w, h = faces[0]

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

            face = gray[y:y + h, x:x + w]

            if count < 20:

                count += 1

                file_path = employee_folder / f"{count}.jpg"

                cv2.imwrite(
                    str(file_path),
                    face
                )

            cv2.putText(
                frame,
                f"Captured: {count}/20",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

        cv2.imshow(
            "Employee Face Registration",
            frame
        )

        if count >= 20:
            break

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()

    if count < 10:

        print("\nNot enough face images captured.")
        print(f"Only {count} images were captured.")
        print("Please register the employee again.")
        return

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO employees
        (
            employee_id,
            name,
            email,
            phone,
            department,
            designation,
            salary,
            photo_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            employee_id,
            name,
            email,
            phone,
            department,
            designation,
            salary,
            str(employee_folder)
        )
    )

    connection.commit()
    connection.close()

    print("\n================================")
    print("       EMPLOYEE REGISTERED")
    print("================================")
    print(f"Employee ID : {employee_id}")
    print(f"Name        : {name}")
    print(f"Department  : {department}")
    print(f"Designation : {designation}")
    print(f"Salary      : Rs.{salary}")
    print(f"Face Images : {count}")
    print(f"Face Folder : {employee_folder}")
    print("================================")
    print("Registration completed successfully!")
    print("================================")


if __name__ == "__main__":
    register_employee()