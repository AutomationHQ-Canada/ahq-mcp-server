import contextlib
import os

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from src.mcp_server import server, app_http_client

session_manager = StreamableHTTPSessionManager(app=server, json_response=False, stateless=True)


@contextlib.asynccontextmanager
async def lifespan(app):
    app_http_client.client = httpx.AsyncClient(limits=httpx.Limits(max_connections=200, max_keepalive_connections=50))
    async with session_manager.run():
        yield
    await app_http_client.client.aclose()
    app_http_client.client = None


async def healthz(request):
    return PlainTextResponse("ok")


app = Starlette(
    routes=[
        Route("/healthz", healthz),
        Mount("/mcp", app=session_manager.handle_request),
    ],
    lifespan=lifespan,
)


def main():
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))


if __name__ == "__main__":
    main()
