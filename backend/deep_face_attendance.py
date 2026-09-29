from pathlib import Path
import time
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import cv2
import numpy as np
import mediapipe as mp
import pyttsx3

from insightface.app import FaceAnalysis
from excel_export import export_database_to_excel

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / "database" / "attendance.db"
EMBEDDINGS_DIR = BASE_DIR / "face_embeddings"

CHECK_IN_DIR = BASE_DIR / "attendance_photos" / "check_in"
CHECK_OUT_DIR = BASE_DIR / "attendance_photos" / "check_out"

LANDMARKER_MODEL = BASE_DIR / "models" / "face_landmarker.task"


# Create required folders
EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
CHECK_IN_DIR.mkdir(parents=True, exist_ok=True)
CHECK_OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SETTINGS
# ============================================================

SIMILARITY_THRESHOLD = 0.55

REQUIRED_CONFIRMATIONS = 5

LIVENESS_TIMEOUT_SECONDS = 30

EAR_THRESHOLD = 0.21
CLOSED_FRAMES_REQUIRED = 2

# If second-largest face is >= 70% of largest face,
# treat it as two prominent faces.
AMBIGUOUS_FACE_RATIO = 0.70

# Largest face must occupy at least 1.5% of image.
MIN_FACE_AREA_RATIO = 0.015

# Prevent repeated voice messages.
VOICE_COOLDOWN_SECONDS = 5


# ============================================================
# VOICE SYSTEM
# ============================================================

last_voice_message = {}


def create_voice_engine():
    """
    There is no persistent pyttsx3 engine.

    A fresh SAPI5 engine is created for every announcement.
    This avoids conflicts with OpenCV, MediaPipe and InsightFace.
    """

    print("Voice announcement system: READY")

    return True


def format_employee_id_for_speech(employee_id):
    """
    Converts:

        EMP001

    into:

        E M P 0 0 1
    """

    return " ".join(str(employee_id))


def employee_voice_prefix(employee_id, name):
    """
    Creates:

        Employee ID E M P 0 0 1, Deepashree B L
    """

    return (
        f"Employee ID "
        f"{format_employee_id_for_speech(employee_id)}, "
        f"{name}"
    )


def speak_message(engine, message, force=False):
    """
    Reliable Windows voice announcement.

    A completely fresh SAPI5 engine is created for every
    announcement.

    force=True bypasses the cooldown. This is used for
    important attendance results such as check-in,
    check-out and already checked-out messages.
    """

    now = time.time()

    last_time = last_voice_message.get(
        message,
        0
    )

    # Prevent repeated messages unless forced.
    if not force:

        if (
            now - last_time
            < VOICE_COOLDOWN_SECONDS
        ):

            return

    last_voice_message[message] = now

    print(
        f"[VOICE] {message}"
    )

    speech_engine = None

    try:

        # ====================================================
        # IMPORTANT:
        # Use the same SAPI5 method that worked in the
        # standalone PowerShell voice test.
        # ====================================================

        speech_engine = pyttsx3.init(
            "sapi5"
        )

        speech_engine.setProperty(
            "rate",
            160
        )

        speech_engine.setProperty(
            "volume",
            1.0
        )

        speech_engine.say(
            message
        )

        # Wait until speech is completely finished.
        speech_engine.runAndWait()

        speech_engine.stop()

        print(
            "[VOICE] Announcement completed."
        )

        # Small gap before computer-vision processing continues.
        time.sleep(0.3)

    except Exception as error:

        print(
            f"[VOICE ERROR] {error}"
        )

    finally:

        if speech_engine is not None:

            try:

                speech_engine.stop()

            except Exception:

                pass


# ============================================================
# TIMEZONE
# ============================================================

try:

    INDIA_TZ = ZoneInfo(
        "Asia/Kolkata"
    )

except Exception:

    INDIA_TZ = None


def get_india_now():

    if INDIA_TZ:

        return datetime.now(
            INDIA_TZ
        )

    return datetime.now()


def get_today_date():

    return get_india_now().strftime(
        "%Y-%m-%d"
    )


def get_current_time():

    return get_india_now().strftime(
        "%H:%M:%S"
    )


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def get_employees():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                employee_id,
                name,
                email,
                phone,
                department,
                designation,
                salary,
                face_encoding,
                photo_path,
                created_at,
                is_active
            FROM employees
            WHERE is_active = 1
            ORDER BY employee_id
            """
        )

        return cursor.fetchall()

    finally:

        connection.close()


def get_today_attendance(
    employee_id
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM attendance
            WHERE employee_id = ?
            AND date = ?
            """,
            (
                employee_id,
                get_today_date(),
            ),
        )

        return cursor.fetchone()

    finally:

        connection.close()


# ============================================================
# CHECK-IN
# ============================================================

def mark_check_in(
    employee_id,
    photo_path
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        today = get_today_date()

        current_time = get_current_time()

        cursor.execute(
            """
            SELECT *
            FROM attendance
            WHERE employee_id = ?
            AND date = ?
            """,
            (
                employee_id,
                today,
            ),
        )

        existing = cursor.fetchone()

        if existing:

            if existing["check_in"]:

                return (
                    False,
                    "ALREADY_CHECKED_IN",
                )

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
                str(photo_path),
            ),
        )

        connection.commit()

        return (
            True,
            "CHECK_IN_SUCCESS",
        )

    except Exception as error:

        print(
            f"Check-in database error: {error}"
        )

        return (
            False,
            "DATABASE_ERROR",
        )

    finally:

        connection.close()


# ============================================================
# CHECK-OUT
# ============================================================

def mark_check_out(
    employee_id,
    photo_path
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        today = get_today_date()

        current_time = get_current_time()

        cursor.execute(
            """
            SELECT *
            FROM attendance
            WHERE employee_id = ?
            AND date = ?
            """,
            (
                employee_id,
                today,
            ),
        )

        existing = cursor.fetchone()

        # No attendance record
        if not existing:

            return (
                False,
                "NO_CHECK_IN",
                0,
            )

        # No check-in
        if not existing["check_in"]:

            return (
                False,
                "NO_CHECK_IN",
                0,
            )

        # Already checked out
        if existing["check_out"]:

            return (
                False,
                "ALREADY_CHECKED_OUT",
                existing["working_hours"] or 0,
            )

        check_in_text = existing[
            "check_in"
        ]

        check_in_time = datetime.strptime(
            check_in_text,
            "%H:%M:%S"
        )

        check_out_time = datetime.strptime(
            current_time,
            "%H:%M:%S"
        )

        # Handle crossing midnight
        if check_out_time < check_in_time:

            check_out_time += timedelta(
                days=1
            )

        difference = (
            check_out_time -
            check_in_time
        )

        working_hours = (
            difference.total_seconds()
            / 3600
        )

        working_hours = round(
            working_hours,
            2
        )

        cursor.execute(
            """
            UPDATE attendance
            SET
                check_out = ?,
                working_hours = ?,
                check_out_photo = ?
            WHERE employee_id = ?
            AND date = ?
            """,
            (
                current_time,
                working_hours,
                str(photo_path),
                employee_id,
                today,
            ),
        )

        connection.commit()

        return (
            True,
            "CHECK_OUT_SUCCESS",
            working_hours,
        )

    except Exception as error:

        print(
            f"Check-out database error: {error}"
        )

        return (
            False,
            "DATABASE_ERROR",
            0,
        )

    finally:

        connection.close()


# ============================================================
# LOAD DEEP FACE EMBEDDINGS
# ============================================================

def load_employee_embeddings():

    embeddings = {}

    employees = get_employees()

    employee_map = {}

    for employee in employees:

        employee_id = employee[
            "employee_id"
        ]

        employee_map[
            str(employee_id)
        ] = {
            "employee_id": employee_id,
            "name": employee["name"],
        }

    for (
        employee_id,
        employee_info
    ) in employee_map.items():

        embedding_file = (
            EMBEDDINGS_DIR /
            f"{employee_id}.npy"
        )

        if not embedding_file.exists():

            print(
                f"Warning: No deep embedding "
                f"found for {employee_id} "
                f"({employee_info['name']})"
            )

            continue

        try:

            embedding = np.load(
                embedding_file
            )

            embedding = np.asarray(
                embedding,
                dtype=np.float32
            )

            norm = np.linalg.norm(
                embedding
            )

            if norm == 0:

                print(
                    f"Warning: Invalid embedding "
                    f"for {employee_id}"
                )

                continue

            embedding = (
                embedding / norm
            )

            embeddings[
                employee_id
            ] = {
                "embedding": embedding,
                "name": employee_info["name"],
            }

        except Exception as error:

            print(
                f"Error loading embedding "
                f"for {employee_id}: {error}"
            )

    print(
        f"Loaded "
        f"{len(embeddings)} "
        f"employee face embeddings."
    )

    return embeddings


# ============================================================
# COSINE SIMILARITY
# ============================================================

def cosine_similarity(
    embedding1,
    embedding2
):

    embedding1 = np.asarray(
        embedding1,
        dtype=np.float32
    )

    embedding2 = np.asarray(
        embedding2,
        dtype=np.float32
    )

    norm1 = np.linalg.norm(
        embedding1
    )

    norm2 = np.linalg.norm(
        embedding2
    )

    if norm1 == 0 or norm2 == 0:

        return 0.0

    embedding1 = (
        embedding1 / norm1
    )

    embedding2 = (
        embedding2 / norm2
    )

    return float(
        np.dot(
            embedding1,
            embedding2
        )
    )


# ============================================================
# SELECT DOMINANT INSIGHTFACE FACE
# ============================================================

def select_dominant_face(
    faces,
    frame_width,
    frame_height
):

    if not faces:

        return (
            None,
            "NO_FACE"
        )

    frame_area = (
        frame_width *
        frame_height
    )

    face_data = []

    for face in faces:

        bbox = face.bbox

        x1, y1, x2, y2 = bbox

        width = max(
            0,
            x2 - x1
        )

        height = max(
            0,
            y2 - y1
        )

        area = (
            width *
            height
        )

        face_data.append(
            (
                area,
                face
            )
        )

    face_data.sort(
        key=lambda item: item[0],
        reverse=True
    )

    largest_area, largest_face = (
        face_data[0]
    )

    largest_ratio = (
        largest_area /
        frame_area
    )

    # Face too far
    if (
        largest_ratio <
        MIN_FACE_AREA_RATIO
    ):

        return (
            None,
            "TOO_FAR"
        )

    # Multiple prominent faces
    if len(face_data) >= 2:

        second_area = (
            face_data[1][0]
        )

        ratio = (
            second_area /
            largest_area
        )

        if (
            ratio >=
            AMBIGUOUS_FACE_RATIO
        ):

            return (
                None,
                "MULTIPLE_PROMINENT"
            )

    return (
        largest_face,
        "OK"
    )


# ============================================================
# SELECT DOMINANT MEDIAPIPE FACE
# ============================================================

def select_dominant_landmarks(
    face_landmarks,
    image_width,
    image_height
):

    if not face_landmarks:

        return (
            None,
            "NO_FACE"
        )

    image_area = (
        image_width *
        image_height
    )

    face_data = []

    for landmarks in face_landmarks:

        xs = [
            point.x
            for point in landmarks
        ]

        ys = [
            point.y
            for point in landmarks
        ]

        min_x = max(
            0,
            min(xs)
        )

        max_x = min(
            1,
            max(xs)
        )

        min_y = max(
            0,
            min(ys)
        )

        max_y = min(
            1,
            max(ys)
        )

        width = (
            max_x -
            min_x
        )

        height = (
            max_y -
            min_y
        )

        area = (
            width *
            height *
            image_area
        )

        face_data.append(
            (
                area,
                landmarks
            )
        )

    face_data.sort(
        key=lambda item: item[0],
        reverse=True
    )

    largest_area, largest_face = (
        face_data[0]
    )

    largest_ratio = (
        largest_area /
        image_area
    )

    if (
        largest_ratio <
        MIN_FACE_AREA_RATIO
    ):

        return (
            None,
            "TOO_FAR"
        )

    if len(face_data) >= 2:

        second_area = (
            face_data[1][0]
        )

        ratio = (
            second_area /
            largest_area
        )

        if (
            ratio >=
            AMBIGUOUS_FACE_RATIO
        ):

            return (
                None,
                "MULTIPLE_PROMINENT"
            )

    return (
        largest_face,
        "OK"
    )


# ============================================================
# DISTANCE BETWEEN LANDMARK POINTS
# ============================================================

def distance(
    point1,
    point2
):

    x1 = point1.x
    y1 = point1.y

    x2 = point2.x
    y2 = point2.y

    return np.sqrt(
        (x1 - x2) ** 2 +
        (y1 - y2) ** 2
    )


# ============================================================
# EYE ASPECT RATIO
# ============================================================

def eye_aspect_ratio(
    landmarks,
    p1,
    p2,
    p3,
    p4,
    p5,
    p6
):

    vertical_1 = distance(
        landmarks[p2],
        landmarks[p6]
    )

    vertical_2 = distance(
        landmarks[p3],
        landmarks[p5]
    )

    horizontal = distance(
        landmarks[p1],
        landmarks[p4]
    )

    if horizontal == 0:

        return 1.0

    return (
        vertical_1 +
        vertical_2
    ) / (
        2.0 *
        horizontal
    )


# ============================================================
# BLINK DETECTION
# ============================================================

def calculate_blink_ear(
    landmarks
):

    left_ear = eye_aspect_ratio(
        landmarks,
        33,
        160,
        158,
        133,
        153,
        144
    )

    right_ear = eye_aspect_ratio(
        landmarks,
        362,
        385,
        387,
        263,
        373,
        380
    )

    return (
        left_ear +
        right_ear
    ) / 2.0


# ============================================================
# LIVENESS VERIFICATION
# ============================================================

def verify_liveness(
    camera,
    landmarker,
    voice_engine
):

    print()
    print("=" * 60)
    print("LIVENESS VERIFICATION")
    print("=" * 60)
    print("Look at the camera.")
    print("Blink naturally.")
    print("Press Q to cancel.")
    print("=" * 60)

    speak_message(
        voice_engine,
        "Liveness verification started. "
        "Please look at the camera and blink naturally.",
        force=True
    )

    start_time = time.time()

    blink_count = 0

    closed_frames = 0

    was_eye_closed = False

    last_status = None

    while True:

        elapsed = (
            time.time() -
            start_time
        )

        if (
            elapsed >
            LIVENESS_TIMEOUT_SECONDS
        ):

            print(
                "Liveness verification timed out."
            )

            speak_message(
                voice_engine,
                "Liveness verification failed. "
                "Please try again.",
                force=True
            )

            return False

        success, frame = (
            camera.read()
        )

        if not success:

            print(
                "Unable to read camera."
            )

            speak_message(
                voice_engine,
                "Unable to access the camera. "
                "Please try again.",
                force=True
            )

            return False

        frame = cv2.flip(
            frame,
            1
        )

        frame_height, frame_width = (
            frame.shape[:2]
        )

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=(
                mp.ImageFormat.SRGB
            ),
            data=rgb
        )

        try:

            result = landmarker.detect(
                mp_image
            )

        except Exception as error:

            print(
                f"Liveness detection error: "
                f"{error}"
            )

            cv2.putText(
                frame,
                "LIVENESS ERROR",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

            cv2.imshow(
                "Liveness Verification",
                frame
            )

            key = (
                cv2.waitKey(1)
                & 0xFF
            )

            if key == ord("q"):

                speak_message(
                    voice_engine,
                    "Liveness verification cancelled.",
                    force=True
                )

                return False

            continue

        face_landmarks = (
            result.face_landmarks
        )

        (
            dominant_landmarks,
            status
        ) = select_dominant_landmarks(
            face_landmarks,
            frame_width,
            frame_height
        )

        # ----------------------------------------------------
        # NO FACE
        # ----------------------------------------------------

        if status == "NO_FACE":

            cv2.putText(
                frame,
                "FACE NOT DETECTED",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2
            )

            if last_status != status:

                speak_message(
                    voice_engine,
                    "Face not detected. "
                    "Please look at the camera."
                )

                last_status = status

        # ----------------------------------------------------
        # MULTIPLE FACES
        # ----------------------------------------------------

        elif (
            status ==
            "MULTIPLE_PROMINENT"
        ):

            cv2.putText(
                frame,
                "TWO PROMINENT FACES DETECTED",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

            if last_status != status:

                speak_message(
                    voice_engine,
                    "Two prominent faces detected. "
                    "Please stand one at a time."
                )

                last_status = status

        # ----------------------------------------------------
        # FACE TOO FAR
        # ----------------------------------------------------

        elif status == "TOO_FAR":

            cv2.putText(
                frame,
                "FACE TOO FAR - MOVE CLOSER",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

            if last_status != status:

                speak_message(
                    voice_engine,
                    "Your face is too far. "
                    "Please move closer to the camera."
                )

                last_status = status

        # ----------------------------------------------------
        # FACE FOUND
        # ----------------------------------------------------

        else:

            last_status = "OK"

            ear = calculate_blink_ear(
                dominant_landmarks
            )

            if ear < EAR_THRESHOLD:

                closed_frames += 1

            else:

                if (
                    closed_frames >=
                    CLOSED_FRAMES_REQUIRED
                ):

                    if not was_eye_closed:

                        blink_count += 1

                        print(
                            f"Blink detected: "
                            f"{blink_count}"
                        )

                    was_eye_closed = True

                closed_frames = 0

            if ear >= EAR_THRESHOLD:

                was_eye_closed = False

            cv2.putText(
                frame,
                f"EAR: {ear:.2f}",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"Blinks: {blink_count}",
                (30, 85),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            if blink_count >= 1:

                print()
                print(
                    "LIVENESS VERIFIED"
                )

                print(
                    f"Blink count: "
                    f"{blink_count}"
                )

                speak_message(
                    voice_engine,
                    "Liveness verification successful.",
                    force=True
                )

                time.sleep(
                    0.5
                )

                cv2.destroyWindow(
                    "Liveness Verification"
                )

                return True

        remaining = max(
            0,
            int(
                LIVENESS_TIMEOUT_SECONDS -
                elapsed
            )
        )

        cv2.putText(
            frame,
            f"Time: {remaining}s",
            (
                30,
                frame_height - 25
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.imshow(
            "Liveness Verification",
            frame
        )

        key = (
            cv2.waitKey(1)
            & 0xFF
        )

        if key == ord("q"):

            speak_message(
                voice_engine,
                "Liveness verification cancelled.",
                force=True
            )

            cv2.destroyWindow(
                "Liveness Verification"
            )

            return False


# ============================================================
# SAVE ATTENDANCE PHOTO
# ============================================================

def save_attendance_photo(
    frame,
    employee_id,
    attendance_type
):

    now = get_india_now()

    timestamp = now.strftime(
        "%Y%m%d_%H%M%S"
    )

    if (
        attendance_type ==
        "check_in"
    ):

        directory = CHECK_IN_DIR

    else:

        directory = CHECK_OUT_DIR

    filename = (
        f"{employee_id}_"
        f"{timestamp}.jpg"
    )

    photo_path = (
        directory /
        filename
    )

    cv2.imwrite(
        str(photo_path),
        frame
    )

    return photo_path


# ============================================================
# FIND BEST MATCH
# ============================================================

def find_best_match(
    face_embedding,
    employee_embeddings
):

    best_employee_id = None

    best_name = None

    best_similarity = -1.0

    for (
        employee_id,
        data
    ) in employee_embeddings.items():

        stored_embedding = (
            data["embedding"]
        )

        similarity = cosine_similarity(
            face_embedding,
            stored_embedding
        )

        if (
            similarity >
            best_similarity
        ):

            best_similarity = (
                similarity
            )

            best_employee_id = (
                employee_id
            )

            best_name = (
                data["name"]
            )

    if (
        best_employee_id is None
        or
        best_similarity <
        SIMILARITY_THRESHOLD
    ):

        return (
            None,
            None,
            best_similarity
        )

    return (
        best_employee_id,
        best_name,
        best_similarity
    )


# ============================================================
# HANDLE ATTENDANCE RESULT
# ============================================================

def handle_attendance(
    frame,
    employee_id,
    name,
    voice_engine
):

    """
    Handles today's attendance.

    Priority:

    1. Already checked out
    2. No attendance -> check-in
    3. Checked in but not checked out -> check-out
    """

    existing = get_today_attendance(
        employee_id
    )

    employee_prefix = employee_voice_prefix(
        employee_id,
        name
    )

    # ========================================================
    # 1. ALREADY CHECKED OUT
    # ========================================================

    if (
        existing is not None
        and existing["check_out"]
    ):

        text = (
            f"{employee_prefix}, "
            "your check-out is already marked."
        )

        print()
        print("=" * 60)
        print("ATTENDANCE STATUS")
        print("=" * 60)
        print(text)

        print(
            f"Check-in: "
            f"{existing['check_in']}"
        )

        print(
            f"Check-out: "
            f"{existing['check_out']}"
        )

        print("=" * 60)

        # FORCE ensures this important message
        # is not blocked by cooldown.
        speak_message(
            voice_engine,
            text,
            force=True
        )

        return True

    # ========================================================
    # 2. NO ATTENDANCE TODAY -> CHECK-IN
    # ========================================================

    if existing is None:

        photo_path = save_attendance_photo(
            frame,
            employee_id,
            "check_in"
        )

        success, message = mark_check_in(
            employee_id,
            photo_path
        )

        if success:

            text = (
                f"{employee_prefix}, "
                "your attendance is marked."
            )

            print()
            print("=" * 60)
            print("ATTENDANCE STATUS")
            print("=" * 60)
            print(text)
            print("=" * 60)

            # FORCE voice announcement.
            speak_message(
                voice_engine,
                text,
                force=True
            )

            return True

        if message == "ALREADY_CHECKED_IN":

            text = (
                f"{employee_prefix}, "
                "your attendance is already marked."
            )

            print()
            print(text)

            speak_message(
                voice_engine,
                text,
                force=True
            )

            return True

        text = (
            f"{employee_prefix}, "
            "your attendance could not be marked. "
            "Please try again."
        )

        print()
        print(text)

        speak_message(
            voice_engine,
            text,
            force=True
        )

        return False

    # ========================================================
    # 3. CHECKED IN BUT NOT CHECKED OUT
    # ========================================================

    if (
        existing["check_in"]
        and not existing["check_out"]
    ):

        photo_path = save_attendance_photo(
            frame,
            employee_id,
            "check_out"
        )

        (
            success,
            message,
            working_hours
        ) = mark_check_out(
            employee_id,
            photo_path
        )

        if success:

            text = (
                f"{employee_prefix}, "
                "your check-out is marked. "
                f"Your working hours are "
                f"{working_hours:.2f} hours."
            )

            print()
            print("=" * 60)
            print("ATTENDANCE STATUS")
            print("=" * 60)
            print(text)
            print("=" * 60)

            # FORCE voice announcement.
            speak_message(
                voice_engine,
                text,
                force=True
            )

            return True

        if message == "ALREADY_CHECKED_OUT":

            text = (
                f"{employee_prefix}, "
                "your check-out is already marked."
            )

            print()
            print(text)

            speak_message(
                voice_engine,
                text,
                force=True
            )

            return True

        if message == "NO_CHECK_IN":

            text = (
                f"{employee_prefix}, "
                "check-out cannot be marked "
                "because your check-in was not found."
            )

            print()
            print(text)

            speak_message(
                voice_engine,
                text,
                force=True
            )

            return False

        text = (
            f"{employee_prefix}, "
            "your check-out could not be marked. "
            "Please try again."
        )

        print()
        print(text)

        speak_message(
            voice_engine,
            text,
            force=True
        )

        return False

    # ========================================================
    # 4. FALLBACK
    # ========================================================

    text = (
        f"{employee_prefix}, "
        "attendance could not be marked. "
        "Please try again."
    )

    print()
    print(text)

    speak_message(
        voice_engine,
        text,
        force=True
    )

    return False


# ============================================================
# RECOGNITION PHASE
# ============================================================

def recognition_phase(
    camera,
    face_app,
    employee_embeddings,
    voice_engine
):

    print()
    print("=" * 60)
    print("FACE RECOGNITION")
    print("=" * 60)
    print(
        "Look at the camera."
    )
    print(
        "Press Q to quit."
    )
    print("=" * 60)

    speak_message(
        voice_engine,
        "Face recognition started. "
        "Please look at the camera.",
        force=True
    )

    confirmation_count = 0

    confirmed_employee_id = None

    confirmed_name = None

    last_unknown_announcement = 0

    last_status = None

    while True:

        success, frame = (
            camera.read()
        )

        if not success:

            print(
                "Unable to read camera."
            )

            speak_message(
                voice_engine,
                "Unable to access the camera. "
                "Please try again.",
                force=True
            )

            return False

        frame = cv2.flip(
            frame,
            1
        )

        frame_height, frame_width = (
            frame.shape[:2]
        )

        try:

            faces = face_app.get(
                frame
            )

        except Exception as error:

            print(
                f"Face recognition error: "
                f"{error}"
            )

            cv2.putText(
                frame,
                "FACE RECOGNITION ERROR",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

            cv2.imshow(
                "Face Recognition Attendance",
                frame
            )

            key = (
                cv2.waitKey(1)
                & 0xFF
            )

            if key == ord("q"):

                return False

            continue

        (
            dominant_face,
            status
        ) = select_dominant_face(
            faces,
            frame_width,
            frame_height
        )

        # ====================================================
        # NO FACE
        # ====================================================

        if status == "NO_FACE":

            confirmation_count = 0

            confirmed_employee_id = None

            confirmed_name = None

            cv2.putText(
                frame,
                "FACE NOT DETECTED",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2
            )

            if last_status != status:

                speak_message(
                    voice_engine,
                    "Face not detected. "
                    "Please look at the camera."
                )

                last_status = status

        # ====================================================
        # MULTIPLE PROMINENT FACES
        # ====================================================

        elif (
            status ==
            "MULTIPLE_PROMINENT"
        ):

            confirmation_count = 0

            confirmed_employee_id = None

            confirmed_name = None

            cv2.putText(
                frame,
                "TWO PROMINENT FACES DETECTED",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 0, 255),
                2
            )

            if last_status != status:

                speak_message(
                    voice_engine,
                    "Two prominent faces detected. "
                    "Please stand one at a time."
                )

                last_status = status

        # ====================================================
        # FACE TOO FAR
        # ====================================================

        elif status == "TOO_FAR":

            confirmation_count = 0

            confirmed_employee_id = None

            confirmed_name = None

            cv2.putText(
                frame,
                "FACE TOO FAR - MOVE CLOSER",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

            if last_status != status:

                speak_message(
                    voice_engine,
                    "Your face is too far. "
                    "Please move closer to the camera."
                )

                last_status = status

        # ====================================================
        # VALID SINGLE FACE
        # ====================================================

        else:

            last_status = "OK"

            embedding = (
                dominant_face.embedding
            )

            (
                employee_id,
                name,
                similarity
            ) = find_best_match(
                embedding,
                employee_embeddings
            )

            # =================================================
            # UNKNOWN FACE
            # =================================================

            if employee_id is None:

                confirmation_count = 0

                confirmed_employee_id = None

                confirmed_name = None

                cv2.putText(
                    frame,
                    "FACE NOT RECOGNISED",
                    (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.85,
                    (0, 0, 255),
                    2
                )

                cv2.putText(
                    frame,
                    "Attendance NOT marked",
                    (30, 85),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (0, 0, 255),
                    2
                )

                now = time.time()

                if (
                    now -
                    last_unknown_announcement
                    >=
                    VOICE_COOLDOWN_SECONDS
                ):

                    speak_message(
                        voice_engine,
                        "Face not recognized. "
                        "Attendance has not been marked.",
                        force=True
                    )

                    last_unknown_announcement = now

            # =================================================
            # MATCHED EMPLOYEE
            # =================================================

            else:

                if (
                    employee_id ==
                    confirmed_employee_id
                ):

                    confirmation_count += 1

                else:

                    confirmed_employee_id = (
                        employee_id
                    )

                    confirmed_name = (
                        name
                    )

                    confirmation_count = 1

                cv2.putText(
                    frame,
                    f"{name}",
                    (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"ID: {employee_id}",
                    (30, 85),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"Similarity: {similarity:.3f}",
                    (30, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    (
                        f"Confirmation: "
                        f"{confirmation_count}/"
                        f"{REQUIRED_CONFIRMATIONS}"
                    ),
                    (30, 155),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 0),
                    2
                )

                # =============================================
                # REQUIRED CONFIRMATIONS REACHED
                # =============================================

                if (
                    confirmation_count >=
                    REQUIRED_CONFIRMATIONS
                ):

                    print()

                    print(
                        f"Face recognized: "
                        f"{employee_id} - "
                        f"{name}"
                    )

                    print(
                        f"Similarity: "
                        f"{similarity:.3f}"
                    )

                    result = (
                        handle_attendance(
                            frame,
                            employee_id,
                            name,
                            voice_engine
                        )
                    )

                    # Give time for announcement.
                    time.sleep(2)

                    return result

        # ====================================================
        # DISPLAY
        # ====================================================

        cv2.imshow(
            "Face Recognition Attendance",
            frame
        )

        key = (
            cv2.waitKey(1)
            & 0xFF
        )

        if key == ord("q"):

            print(
                "Attendance process cancelled."
            )

            speak_message(
                voice_engine,
                "Attendance process cancelled.",
                force=True
            )

            return False


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("SMART ATTENDANCE SYSTEM")
    print("FACE RECOGNITION + LIVENESS + VOICE")
    print("=" * 70)

    # ========================================================
    # CREATE VOICE SYSTEM
    # ========================================================

    voice_engine = (
        create_voice_engine()
    )

    # ========================================================
    # LOAD EMPLOYEE EMBEDDINGS
    # ========================================================

    employee_embeddings = (
        load_employee_embeddings()
    )

    if not employee_embeddings:

        print()
        print(
            "ERROR: No employee face embeddings found."
        )

        print(
            "Please register an employee first."
        )

        speak_message(
            voice_engine,
            "No employee face data found. "
            "Please register an employee first.",
            force=True
        )

        return

    # ========================================================
    # CHECK LANDMARKER MODEL
    # ========================================================

    if not LANDMARKER_MODEL.exists():

        print()
        print(
            "ERROR: MediaPipe face landmarker model "
            "not found."
        )

        print(
            "Expected location:"
        )

        print(
            LANDMARKER_MODEL
        )

        speak_message(
            voice_engine,
            "The liveness model was not found.",
            force=True
        )

        return

    # ========================================================
    # INITIALIZE INSIGHTFACE
    # ========================================================

    print()
    print(
        "Loading InsightFace..."
    )

    try:

        face_app = FaceAnalysis(
            name="buffalo_l",
            providers=[
                "CPUExecutionProvider"
            ]
        )

        face_app.prepare(
            ctx_id=0,
            det_size=(640, 640)
        )

    except Exception as error:

        print()
        print(
            f"InsightFace initialization error: "
            f"{error}"
        )

        speak_message(
            voice_engine,
            "Face recognition system "
            "could not be started.",
            force=True
        )

        return

    print(
        "InsightFace loaded successfully."
    )

    # ========================================================
    # INITIALIZE MEDIAPIPE LANDMARKER
    # ========================================================

    print()
    print(
        "Loading MediaPipe liveness model..."
    )

    try:

        base_options = (
            python.BaseOptions(
                model_asset_path=str(
                    LANDMARKER_MODEL
                )
            )
        )

        options = (
            vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=(
                    vision.RunningMode.IMAGE
                ),
                num_faces=5,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5
            )
        )

        landmarker = (
            vision.FaceLandmarker
            .create_from_options(
                options
            )
        )

    except Exception as error:

        print()
        print(
            f"MediaPipe initialization error: "
            f"{error}"
        )

        speak_message(
            voice_engine,
            "Liveness verification "
            "could not be started.",
            force=True
        )

        return

    print(
        "MediaPipe liveness model "
        "loaded successfully."
    )

    # ========================================================
    # OPEN CAMERA
    # ========================================================

    print()
    print(
        "Opening camera..."
    )

    camera = cv2.VideoCapture(
        0
    )

    if not camera.isOpened():

        print()
        print(
            "ERROR: Could not open webcam."
        )

        speak_message(
            voice_engine,
            "Unable to access the camera. "
            "Please check your webcam.",
            force=True
        )

        return

    camera.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    camera.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )

    print(
        "Camera opened successfully."
    )

    try:

        # ====================================================
        # STAGE 1 - LIVENESS
        # ====================================================

        liveness_verified = (
            verify_liveness(
                camera,
                landmarker,
                voice_engine
            )
        )

        if not liveness_verified:

            print()
            print(
                "Liveness verification failed."
            )

            return

        # ====================================================
        # STAGE 2 - FACE RECOGNITION
        # ====================================================

        recognition_phase(
            camera,
            face_app,
            employee_embeddings,
            voice_engine
        )

    except KeyboardInterrupt:

        print()
        print(
            "Program interrupted."
        )

        speak_message(
            voice_engine,
            "Attendance system stopped.",
            force=True
        )

    except Exception as error:

        print()
        print(
            "Unexpected error:"
        )

        print(
            error
        )

        speak_message(
            voice_engine,
            "An unexpected error occurred. "
            "Please try again.",
            force=True
        )

    finally:

        # ====================================================
        # CLEANUP
        # ====================================================

        camera.release()

        cv2.destroyAllWindows()

        try:

            landmarker.close()

        except Exception:

            pass

        # ====================================================
        # UPDATE EXCEL
        # ====================================================

        try:

            export_database_to_excel()

            print()
            print(
                "Excel attendance report updated."
            )

        except Exception as error:

            print(
                f"Excel export warning: {error}"
            )

        # No persistent pyttsx3 engine to stop.

        print()
        print("=" * 70)
        print(
            "SMART ATTENDANCE SYSTEM STOPPED"
        )
        print("=" * 70)


# ============================================================
# RUN PROGRAM
# ============================================================

if __name__ == "__main__":

    main()


