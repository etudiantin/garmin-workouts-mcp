import logging
import os

from garmin_workouts_mcp.main import mcp, login
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv("API_TOKEN", "")

_garth_ready = False
_garth_error: str | None = None

try:
    login()
    _garth_ready = True
    logger.info("Garmin session loaded successfully.")
except Exception as exc:
    _garth_error = str(exc)
    logger.error("Garmin login failed at startup: %s", _garth_error)
    logger.error(
        "The server will start but all Garmin tools will return an error. "
        "Fix the garth tokens and restart the container."
    )


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not API_TOKEN:
            return JSONResponse({"error": "API_TOKEN not configured"}, status_code=500)
        auth_header = request.headers.get("Authorization", "")
        auth_query = request.query_params.get("token", "")
        if auth_header != f"Bearer {API_TOKEN}" and auth_query != API_TOKEN:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


host = os.getenv("MCP_HOST", "0.0.0.0")
port = int(os.getenv("MCP_PORT", "8001"))
path = os.getenv("MCP_PATH", "/")

app = mcp.http_app(path=path)
app.add_middleware(BearerAuthMiddleware)
uvicorn.run(app, host=host, port=port)
