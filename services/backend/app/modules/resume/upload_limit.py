"""Bound multipart bytes before Starlette can spool an oversized resume to disk."""

from uuid import uuid4

from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse


class UploadBodyLimit:
    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes + 64 * 1024

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/v1/resumes":
            return await self.app(scope, receive, send)
        total = 0
        exceeded = False
        sent = False

        async def bounded_receive():
            nonlocal total, exceeded
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                exceeded = True
                # Starlette closes its partial temporary files for this exception.
                raise MultiPartException("Upload limit exceeded.")
            return message

        async def bounded_send(message):
            nonlocal sent
            if not exceeded:
                await send(message)
            elif not sent:
                sent = True
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": "The upload exceeds the request limit.",
                            "retryable": False,
                            "request_id": str(uuid4()),
                        }
                    },
                )
                await response(scope, receive, send)

        await self.app(scope, bounded_receive, bounded_send)
