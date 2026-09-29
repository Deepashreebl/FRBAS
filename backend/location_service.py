from typing import List, Tuple
import math


# ============================================================
# BEL BENGALURU CAMPUS GEOFENCE
# ============================================================

BEL_LOCATION_NAME = "Bharat Electronics Limited - Bengaluru Complex"
BEL_ADDRESS = "Jalahalli Post, Bengaluru - 560013"


# ------------------------------------------------------------
# IMPORTANT:
# These are NOT guessed coordinates.
#
# Add the VERIFIED BEL CAMPUS boundary coordinates here.
#
# Format:
# [
#     (latitude, longitude),
#     (latitude, longitude),
#     ...
# ]
#
# The points must go around the entire campus boundary
# in clockwise or anti-clockwise order.
# ------------------------------------------------------------

BEL_CAMPUS_POLYGON: List[Tuple[float, float]] = []


# ============================================================
# DISTANCE CALCULATION
# ============================================================

def calculate_distance(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float
) -> float:

    earth_radius = 6371000

    lat1 = math.radians(latitude1)
    lat2 = math.radians(latitude2)

    delta_lat = math.radians(latitude2 - latitude1)
    delta_lon = math.radians(longitude2 - longitude1)

    a = (
        math.sin(delta_lat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius * c


# ============================================================
# POINT INSIDE POLYGON
# ============================================================

def point_inside_polygon(
    latitude: float,
    longitude: float,
    polygon: List[Tuple[float, float]]
) -> bool:

    if len(polygon) < 3:
        return False

    inside = False

    j = len(polygon) - 1

    for i in range(len(polygon)):

        latitude_i, longitude_i = polygon[i]
        latitude_j, longitude_j = polygon[j]

        intersects = (
            (longitude_i > longitude) !=
            (longitude_j > longitude)
        ) and (
            latitude <
            (
                (latitude_j - latitude_i)
                * (longitude - longitude_i)
                /
                (longitude_j - longitude_i)
                +
                latitude_i
            )
        )

        if intersects:
            inside = not inside

        j = i

    return inside


# ============================================================
# GEOFENCE VERIFICATION
# ============================================================

def verify_bel_location(
    latitude: float,
    longitude: float
) -> dict:

    # Basic GPS validation
    if not (-90 <= latitude <= 90):
        return {
            "allowed": False,
            "message": "Invalid latitude received."
        }

    if not (-180 <= longitude <= 180):
        return {
            "allowed": False,
            "message": "Invalid longitude received."
        }

    # Do not allow attendance until the real boundary
    # has been configured.
    if len(BEL_CAMPUS_POLYGON) < 3:

        return {
            "allowed": False,
            "message": (
                "BEL campus boundary is not configured yet. "
                "Attendance is blocked for safety."
            ),
            "latitude": latitude,
            "longitude": longitude
        }

    inside = point_inside_polygon(
        latitude,
        longitude,
        BEL_CAMPUS_POLYGON
    )

    if inside:

        return {
            "allowed": True,
            "message": (
                "Location verified. "
                "You are inside the BEL attendance area."
            ),
            "latitude": latitude,
            "longitude": longitude
        }

    return {
        "allowed": False,
        "message": (
            "Attendance is not allowed outside "
            "the BEL attendance area."
        ),
        "latitude": latitude,
        "longitude": longitude
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("BEL GPS GEOFENCE SERVICE")
    print("=" * 70)

    print()
    print("Location :", BEL_LOCATION_NAME)
    print("Address  :", BEL_ADDRESS)
    print()

    if len(BEL_CAMPUS_POLYGON) < 3:
        print("STATUS: BEL CAMPUS POLYGON NOT CONFIGURED")
        print()
        print(
            "Attendance will remain BLOCKED until "
            "verified boundary coordinates are added."
        )
    else:
        print(
            f"Boundary points loaded: "
            f"{len(BEL_CAMPUS_POLYGON)}"
        )

    print("=" * 70)