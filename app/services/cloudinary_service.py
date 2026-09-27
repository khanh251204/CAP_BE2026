import io
from typing import Dict, Any, Optional
import cloudinary.uploader
from app.configs.cloudinary_config import CLOUDINARY_NAME


def upload_voice_audio(
    file_bytes: bytes,
    filename: str = "voice.wav",
    folder: str = "voice_cashbook/audio"
) -> Dict[str, Any]:
    """
    Tải file audio lên Cloudinary dưới resource_type='video' (Cloudinary quản lý audio qua video player / processor).
    Trả về dict chứa secure_url, duration, public_id, format, bytes.
    """
    file_obj = io.BytesIO(file_bytes)
    file_obj.name = filename

    upload_result = cloudinary.uploader.upload(
        file_obj,
        resource_type="auto",
        folder=folder,
        overwrite=True
    )

    return {
        "secure_url": upload_result.get("secure_url"),
        "url": upload_result.get("url"),
        "duration": upload_result.get("duration"),
        "public_id": upload_result.get("public_id"),
        "format": upload_result.get("format"),
        "bytes": upload_result.get("bytes"),
    }
