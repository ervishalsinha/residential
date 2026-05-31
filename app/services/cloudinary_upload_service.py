import base64
import binascii
import io
from uuid import uuid4

import cloudinary
import cloudinary.uploader

from app.core.config import get_settings

UPLOAD_TYPE_TO_FOLDER = {
    "profiles": "profiles",
    "properties": "properties",
    "complaints": "complaints",
    "notices": "notices",
    "rent-proofs": "rent-proofs",
}


class ImageUploadError(Exception):
    pass


_cloudinary_configured = False


def _configure_cloudinary() -> None:
    global _cloudinary_configured
    if _cloudinary_configured:
        return

    settings = get_settings()
    if not settings.cloudinary_cloud_name or not settings.cloudinary_api_key or not settings.cloudinary_api_secret:
        raise ImageUploadError("Cloudinary is not configured on the server")

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    _cloudinary_configured = True


def _normalize_mime_type(raw_mime_type: str | None) -> str:
    mime_type = (raw_mime_type or "image/jpeg").strip().lower()
    if mime_type in {"png", "image/png"}:
        return "image/png"
    if mime_type in {"webp", "image/webp"}:
        return "image/webp"
    return "image/jpeg"


def _decode_base64_image(raw_base64: str) -> bytes:
    base64_value = (raw_base64 or "").strip()
    if not base64_value:
        raise ImageUploadError("image_base64 is required")

    if "," in base64_value and base64_value.lower().startswith("data:"):
        base64_value = base64_value.split(",", 1)[1]

    try:
        return base64.b64decode(base64_value, validate=True)
    except (binascii.Error, ValueError):
        raise ImageUploadError("Invalid base64 image payload")


def _folder_for_upload_type(upload_type: str) -> str:
    settings = get_settings()
    if upload_type not in UPLOAD_TYPE_TO_FOLDER:
        raise ImageUploadError("Unsupported upload type")
    return f"{settings.cloudinary_base_folder.rstrip('/')}/{UPLOAD_TYPE_TO_FOLDER[upload_type]}"


def upload_image_base64(*, image_base64: str, upload_type: str, mime_type: str | None = None) -> str:
    _configure_cloudinary()

    image_bytes = _decode_base64_image(image_base64)
    settings = get_settings()
    if len(image_bytes) > settings.image_upload_max_bytes:
        max_mb = settings.image_upload_max_bytes / (1024 * 1024)
        raise ImageUploadError(f"Image too large. Max {int(max_mb)}MB allowed")

    folder = _folder_for_upload_type(upload_type)
    normalized_mime_type = _normalize_mime_type(mime_type)

    try:
        response = cloudinary.uploader.upload(
            io.BytesIO(image_bytes),
            folder=folder,
            resource_type="image",
            public_id=f"img_{uuid4().hex}",
            overwrite=False,
            invalidate=False,
            type="upload",
            format=normalized_mime_type.split("/")[-1],
        )
    except Exception as exc:
        raise ImageUploadError("Failed to upload image") from exc

    secure_url = str(response.get("secure_url") or "").strip()
    if not secure_url:
        raise ImageUploadError("Cloudinary did not return a secure URL")
    return secure_url
