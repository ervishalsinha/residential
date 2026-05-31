from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models import User
from app.schemas.domain import ImageUploadRequest
from app.services.cloudinary_upload_service import ImageUploadError, upload_image_base64

router = APIRouter()


@router.post("/images")
def upload_image(
    payload: ImageUploadRequest,
    user: User = Depends(get_current_user),
):
    del user
    try:
        image_url = upload_image_base64(
            image_base64=payload.image_base64,
            mime_type=payload.mime_type,
            upload_type=payload.upload_type,
        )
    except ImageUploadError as exc:
        detail = str(exc)
        status_code = 400
        if detail in {"Cloudinary is not configured on the server", "Failed to upload image", "Cloudinary did not return a secure URL"}:
            status_code = 502
        raise HTTPException(status_code=status_code, detail=detail)

    return {
        "image_url": image_url,
        # Keep old key for backward compatibility with existing clients.
        "proof_image_url": image_url,
        "upload_type": payload.upload_type,
    }
