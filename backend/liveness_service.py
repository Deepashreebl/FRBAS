import cv2
import time
import numpy as np

from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import mediapipe as mp


# ---------------------------------------------------------
# MODEL PATH
# ---------------------------------------------------------
MODEL_PATH = "models/face_landmarker.task"


# ---------------------------------------------------------
# FACE LANDMARKER SETUP
# ---------------------------------------------------------
base_options = python.BaseOptions(
    model_asset_path=MODEL_PATH
)

options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_faces=1,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)

landmarker = vision.FaceLandmarker.create_from_options(options)


# ---------------------------------------------------------
# EYE LANDMARK INDICES
# MediaPipe Face Landmarker uses the same general
# eye landmark layout as the Face Mesh model.
# ---------------------------------------------------------

LEFT_EYE = [
    33, 160, 158, 133, 153, 144
]

RIGHT_EYE = [
    362, 385, 387, 263, 373, 380
]


# ---------------------------------------------------------
# CALCULATE EYE ASPECT RATIO
# ---------------------------------------------------------
def eye_aspect_ratio(landmarks, eye_indices):

    points = []

    for index in eye_indices:
        landmark = landmarks[index]

        points.append(
            np.array(
                [landmark.x, landmark.y],
                dtype=np.float32
            )
        )

    p1, p2, p3, p4, p5, p6 = points

    vertical_1 = np.linalg.norm(p2 - p6)
    vertical_2 = np.linalg.norm(p3 - p5)

    horizontal = np.linalg.norm(p1 - p4)

    if horizontal == 0:
        return 0.0

    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)

    return ear


# ---------------------------------------------------------
# LIVENESS TEST
# ---------------------------------------------------------
def run_liveness_test():

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("ERROR: Could not open camera.")
        return False

    print()
    print("========================================")
    print("      LIVENESS / BLINK TEST")
    print("========================================")
    print()
    print("Look at the camera.")
    print("Blink naturally.")
    print("Press Q to quit.")
    print()

    blink_count = 0

    eye_closed_frames = 0
    blink_in_progress = False

    start_time = time.time()

    timestamp_ms = 0

    # EAR threshold.
    # This can be adjusted after testing.
    EAR_THRESHOLD = 0.21

    # Number of consecutive closed-eye frames
    # required to count a blink.
    CLOSED_FRAMES_REQUIRED = 2

    while True:

        success, frame = camera.read()

        if not success:
            print("ERROR: Could not read camera frame.")
            break

        frame = cv2.flip(frame, 1)

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        timestamp_ms += 33

        result = landmarker.detect_for_video(
            mp_image,
            timestamp_ms
        )

        status = "NO FACE"

        if result.face_landmarks:

            landmarks = result.face_landmarks[0]

            left_ear = eye_aspect_ratio(
                landmarks,
                LEFT_EYE
            )

            right_ear = eye_aspect_ratio(
                landmarks,
                RIGHT_EYE
            )

            average_ear = (
                left_ear + right_ear
            ) / 2.0

            # -------------------------------------------------
            # BLINK DETECTION
            # -------------------------------------------------

            if average_ear < EAR_THRESHOLD:

                eye_closed_frames += 1

                status = "EYES CLOSED"

            else:

                if (
                    eye_closed_frames
                    >= CLOSED_FRAMES_REQUIRED
                    and not blink_in_progress
                ):

                    blink_count += 1
                    blink_in_progress = True

                eye_closed_frames = 0

                if average_ear >= EAR_THRESHOLD:

                    blink_in_progress = False

                status = "FACE DETECTED"

            # Display EAR
            cv2.putText(
                frame,
                f"EAR: {average_ear:.3f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

        # -----------------------------------------------------
        # DISPLAY BLINK COUNT
        # -----------------------------------------------------

        cv2.putText(
            frame,
            f"Blinks: {blink_count}",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            status,
            (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )

        # -----------------------------------------------------
        # LIVENESS STATUS
        # -----------------------------------------------------

        if blink_count >= 1:

            cv2.putText(
                frame,
                "LIVENESS VERIFIED",
                (20, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                3
            )

        else:

            cv2.putText(
                frame,
                "PLEASE BLINK",
                (20, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        cv2.imshow(
            "Smart Attendance - Liveness Test",
            frame
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):

            break

        # Automatically stop after 30 seconds
        if time.time() - start_time > 30:

            break

    camera.release()

    cv2.destroyAllWindows()

    landmarker.close()

    print()
    print("========================================")

    if blink_count >= 1:

        print("LIVENESS VERIFIED")
        print(f"Blink count: {blink_count}")

        return True

    else:

        print("LIVENESS NOT VERIFIED")
        print("No blink detected.")

        return False


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
if __name__ == "__main__":

    run_liveness_test()