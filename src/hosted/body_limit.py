import json


class BodySizeLimitMiddleware:
    """
    Rejects oversized request bodies with 413 before they reach dispatch. Content-Length is
    checked up front; chunked/streamed bodies are counted as they arrive and the connection is
    cut once the limit is crossed (a 413 is sent only if the response hasn't started, which for
    this app is always the case — nothing streams a response while still reading the request).
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = next(
            (v for k, v in scope.get("headers", []) if k == b"content-length"), None
        )
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    await self._send_413(send)
                    return
            except ValueError:
                pass

        received = 0
        limit_hit = False

        async def counting_receive():
            nonlocal received, limit_hit
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    limit_hit = True
                    # Present the truncated stream as complete; the guard below answers 413.
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        response_started = False
        sent_413 = False

        async def guarding_send(message):
            nonlocal response_started, sent_413
            if limit_hit and not response_started:
                sent_413 = True
                response_started = True
                await self._send_413(send)
                return
            if sent_413:
                # We already answered 413; swallow the app's response to the truncated body.
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        await self.app(scope, counting_receive, guarding_send)

    @staticmethod
    async def _send_413(send):
        body = json.dumps({"error": "request body too large"}).encode()
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})
