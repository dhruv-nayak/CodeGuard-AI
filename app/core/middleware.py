from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Small single-process limiter; use a gateway/Redis limiter for multi-worker deployments."""

    def __init__(
        self, app, requests_per_minute: int = 120, auth_requests_per_minute: int = 10,
        max_body_bytes: int = 1_000_000, enable_hsts: bool = False,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.auth_requests_per_minute = auth_requests_per_minute
        self.max_body_bytes = max_body_bytes
        self.enable_hsts = enable_hsts
        self.events = defaultdict(deque)
        self.lock = Lock()

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))[:100]
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_bytes:
                    return JSONResponse(
                        {"detail": "Request body is too large.", "request_id": request_id},
                        status_code=413,
                    )
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid Content-Length header.", "request_id": request_id},
                    status_code=400,
                )

        if request.url.path.startswith("/api/"):
            identity = request.client.host if request.client else "unknown"
            is_auth = request.url.path in {"/api/v1/auth/login", "/api/v1/auth/register"}
            limit = self.auth_requests_per_minute if is_auth else self.requests_per_minute
            key = f"{identity}:{'auth' if is_auth else 'api'}"
            now = monotonic()
            with self.lock:
                bucket = self.events[key]
                while bucket and now - bucket[0] >= 60:
                    bucket.popleft()
                if len(bucket) >= limit:
                    response = JSONResponse(
                        {
                            "detail": "Rate limit exceeded. Please try again later.",
                            "request_id": request_id,
                        },
                        status_code=429,
                        headers={"Retry-After": str(max(1, int(60 - (now - bucket[0]))))},
                    )
                    return self._secure(response, request_id)
                bucket.append(now)

        try:
            response: Response = await call_next(request)
        except Exception:
            # Avoid returning internal exception details to clients.
            response = JSONResponse(
                {"detail": "Internal server error.", "request_id": request_id},
                status_code=500,
            )
        return self._secure(response, request_id)

    def _secure(self, response: Response, request_id: str) -> Response:
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
