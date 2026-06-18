from pydantic import BaseModel


class UploadResponse(BaseModel):
    status: str
    original_filename: str
    safe_original_filename: str
    stored_filename: str
    size_bytes: int
    detected_mime: str
