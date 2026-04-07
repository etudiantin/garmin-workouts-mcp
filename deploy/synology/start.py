import os
from garmin_workouts_mcp.main import mcp, login
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

API_TOKEN = os.getenv("API_TOKEN", "")

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not API_TOKEN:
            return JSONResponse({"error": "API_TOKEN not configured"}, status_code=500)
        auth_header = request.headers.get("Authorization", "")
        auth_query = request.query_params.get("token", "")
        if auth_header != f"Bearer {API_TOKEN}" and auth_query != API_TOKEN:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

# Charger les tokens garth AVANT d'accepter des connexions
login()

host = os.getenv("MCP_HOST", "0.0.0.0")
port = int(os.getenv("MCP_PORT", "8001"))
path = os.getenv("MCP_PATH", "/")

app = mcp.http_app(path=path)
app.add_middleware(BearerAuthMiddleware)
uvicorn.run(app, host=host, port=port)
