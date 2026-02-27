import time
import uuid
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt
from opentelemetry import trace

router = APIRouter()
tracer = trace.get_tracer(__name__)

SECRET_KEY = "mock-secret-key-for-demo-only"
ALGORITHM = "HS256"
MOCK_REMOTE_AUTH_URL = "http://localhost:9000/mock/auth"

MOCK_USERS = {
    "admin": "password123",
    "user": "secret",
    "demo": "demo",
}


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    username: str


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    with tracer.start_as_current_span("auth.login") as span:
        span.set_attribute("auth.username", request.username)

        # Simulate call to remote authentication service
        span.add_event("Calling remote authentication service", {
            "remote_url": MOCK_REMOTE_AUTH_URL
        })

        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                # Attempt to call the mock remote auth service
                response = await client.post(
                        MOCK_REMOTE_AUTH_URL,
                    json={"username": request.username, "password": request.password}
                )
                span.add_event("Remote auth service responded", {"status": response.status_code})
            except (httpx.ConnectError, httpx.TimeoutException):
                # Fallback to local mock validation when remote is unavailable
                span.add_event("Remote auth unavailable, using local mock")

        # Validate credentials against mock user store
        stored_password = MOCK_USERS.get(request.username)
        if not stored_password or stored_password != request.password:
            span.set_attribute("auth.success", False)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Generate JWT token
        expiry = int(time.time()) + 3600
        payload = {
            "sub": request.username,
            "jti": str(uuid.uuid4()),
            "iat": int(time.time()),
            "exp": expiry,
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        span.set_attribute("auth.success", True)
        span.set_attribute("auth.token_id", payload["jti"])

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=3600,
            username=request.username,
        )
