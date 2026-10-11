
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY or not SUPABASE_BUCKET:
    raise RuntimeError(
        "Supabase configuration is incomplete. "
        "Check SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_BUCKET."
    )

_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def upload_image(object_key: str, image_bytes: bytes) -> None:
    if not image_bytes:
        raise ValueError("Cannot upload an empty image.")

    _client.storage.from_(SUPABASE_BUCKET).upload(
        path=object_key,
        file=image_bytes,
        file_options={
            "content-type": "image/jpeg",
            "upsert": "true",
        },
    )


def download_image(object_key: str) -> bytes:
    if not object_key or object_key.startswith("/"):
        raise ValueError("Invalid storage object key.")

    return _client.storage.from_(SUPABASE_BUCKET).download(object_key)
