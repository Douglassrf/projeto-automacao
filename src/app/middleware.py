from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings


class UploadSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.endswith("/upload"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > get_settings().upload_max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Upload excede o limite máximo configurado."},
                )
        return await call_next(request)
