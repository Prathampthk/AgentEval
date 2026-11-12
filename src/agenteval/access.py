"""Optional single-owner HTTP access gate; deployment still requires trusted TLS ingress."""

import base64
import binascii
import secrets

from starlette.responses import JSONResponse


def validate_access_token(token):
    if token and (not 32 <= len(token) <= 256 or any(not 33 <= ord(c) <= 126 for c in token)):
        raise ValueError(
            "Access token must contain 32–256 printable ASCII characters without spaces"
        )


class OwnerAccess:
    def __init__(self, app, token):
        validate_access_token(token)
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if not self.token or scope["type"] != "http" or scope["path"] == "/health/live":
            return await self.app(scope, receive, send)
        headers = [value for name, value in scope["headers"] if name.lower() == b"authorization"]
        supplied = ""
        if len(headers) == 1:
            try:
                scheme, encoded = headers[0].decode("ascii").split(" ", 1)
                if scheme.lower() == "basic":
                    user, password = (
                        base64.b64decode(encoded, validate=True).decode("ascii").split(":", 1)
                    )
                    if user == "owner":
                        supplied = password
            except (ValueError, UnicodeError, binascii.Error):
                pass
        if not secrets.compare_digest(supplied, self.token):
            return await JSONResponse(
                {"detail": "Authentication required"},
                401,
                headers={
                    "WWW-Authenticate": 'Basic realm="AgentEval", charset="UTF-8"',
                    "Cache-Control": "no-store",
                },
            )(scope, receive, send)

        async def private_response(message):
            if message["type"] == "http.response.start":
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"
                ]
                message = {**message, "headers": headers + [(b"cache-control", b"no-store")]}
            await send(message)

        await self.app(scope, receive, private_response)
